import json
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select, desc

from server import caption_builder, enricher, fetcher, publisher, renderer, uploader
from server.database import get_engine
from server.models import Card, Fighter, FighterQueue, FighterProfile, InstagramPost

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Return the global scheduler instance, creating it if necessary."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def load_scheduler_config() -> dict:
    """Load scheduler config from data/scheduler_config.json.

    Returns defaults if the file does not exist or is malformed.
    Default: enabled, runs Mon–Fri at 09:00.
    """
    defaults = {
        "enabled": True,
        "days": ["mon", "tue", "wed", "thu", "fri"],
        "time": "09:00",
        "timezone": "UTC",
    }
    config_path = Path("data/scheduler_config.json")
    if not config_path.exists():
        return defaults
    try:
        data = json.loads(config_path.read_text())
        if not isinstance(data.get("days"), list) or not data.get("time"):
            return defaults
        return data
    except (json.JSONDecodeError, KeyError):
        logger.warning("scheduler_config.json is malformed — using defaults")
        return defaults


def save_scheduler_config(config: dict) -> None:
    """Persist scheduler config to data/scheduler_config.json."""
    config_path = Path("data/scheduler_config.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))


def _build_cron_kwargs(config: dict) -> dict:
    """Convert config dict into APScheduler cron trigger kwargs.

    Args:
        config: dict with keys 'days' (list of APScheduler day abbreviations),
                'time' (HH:MM 24-hour string), and 'timezone' (IANA timezone name).

    Returns:
        dict of kwargs for scheduler.add_job(trigger='cron', **kwargs)
    """
    hour, minute = config["time"].split(":")
    day_of_week = ",".join(config["days"])  # e.g. "mon,wed,fri"
    return {
        "hour": int(hour),
        "minute": int(minute),
        "day_of_week": day_of_week,
        "timezone": config.get("timezone", "UTC"),
    }


def start_scheduler() -> None:
    """Start the scheduler. Reads config from data/scheduler_config.json at startup.

    Called once at app startup via the FastAPI lifespan context manager.
    If the config file does not exist, defaults to Mon–Fri at 09:00.
    """
    config = load_scheduler_config()
    scheduler = get_scheduler()

    if config.get("enabled", True) and config.get("days"):
        cron_kwargs = _build_cron_kwargs(config)
        scheduler.add_job(
            process_next_queued_fighter,
            trigger="cron",
            id="queue_job",
            replace_existing=True,
            **cron_kwargs,
        )
        logger.info(
            "Scheduler started — days=%s time=%s",
            config["days"],
            config["time"],
        )
    else:
        logger.info("Scheduler started but disabled — no job scheduled")

    scheduler.start()


def apply_scheduler_config(config: dict) -> None:
    """Apply a new config to the running scheduler without restarting the app.

    Called by the API when the user saves scheduler settings from the UI.
    Persists the config to disk, then reschedules or removes the job live.

    Args:
        config: dict with keys:
            enabled (bool)  — whether the scheduler should run
            days (list[str]) — APScheduler day abbreviations e.g. ["mon", "wed", "fri"]
            time (str)      — HH:MM 24-hour wall-clock time e.g. "09:00"
    """
    save_scheduler_config(config)
    scheduler = get_scheduler()

    if config.get("enabled", True) and config.get("days"):
        cron_kwargs = _build_cron_kwargs(config)
        scheduler.add_job(
            process_next_queued_fighter,
            trigger="cron",
            id="queue_job",
            replace_existing=True,
            **cron_kwargs,
        )
        logger.info(
            "Scheduler rescheduled — days=%s time=%s",
            config["days"],
            config["time"],
        )
    else:
        try:
            scheduler.remove_job("queue_job")
            logger.info("Scheduler job removed — scheduler disabled or no days selected")
        except Exception:
            pass  # Job may not exist if it was never scheduled


def stop_scheduler() -> None:
    """Stop the scheduler. Called at app shutdown."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


async def process_next_queued_fighter() -> dict[str, Any] | None:
    """Pick the next pending fighter from the queue and run the full pipeline.

    Skips fighters that already have an InstagramPost linked to their Fighter row.
    Returns a summary dict on success, None if the queue is empty.
    """
    engine = get_engine()

    with Session(engine) as session:
        next_item = session.exec(
            select(FighterQueue)
            .where(FighterQueue.status == "pending")
            .order_by(desc(FighterQueue.priority), FighterQueue.added_at)
            .limit(1)
        ).first()

        if not next_item:
            logger.info("Queue is empty — nothing to process")
            return None

        already_posted = _has_been_posted(session, next_item.fighter_name)
        if already_posted:
            logger.info("Fighter %s already posted — marking done", next_item.fighter_name)
            next_item.status = "done"
            next_item.processed_at = datetime.now(UTC)
            session.add(next_item)
            session.commit()
            return None

        # Mark as processing to prevent duplicate runs
        next_item.status = "processing"
        session.add(next_item)
        session.commit()
        fighter_name = next_item.fighter_name
        queue_id = next_item.id

    # Run pipeline outside the session to avoid long-held locks
    try:
        logger.info("Queue: starting pipeline for %s", fighter_name)
        result = await _run_pipeline(fighter_name)
        logger.info(
            "Queue: pipeline complete for %s — post ID %s",
            fighter_name,
            result["instagram_post_id"],
        )

        with Session(engine) as session:
            item = session.get(FighterQueue, queue_id)
            item.status = "done"
            item.processed_at = datetime.now(UTC)
            session.add(item)
            session.commit()

        return result

    except Exception as e:
        logger.error("Queue: pipeline failed for %s: %s", fighter_name, e)
        with Session(engine) as session:
            item = session.get(FighterQueue, queue_id)
            item.status = "failed"
            item.error_message = str(e)
            item.processed_at = datetime.now(UTC)
            session.add(item)
            session.commit()
        return None


def _has_been_posted(session: Session, fighter_name: str) -> bool:
    """Return True if this fighter has at least one successful Instagram post."""
    fighter = session.exec(
        select(Fighter).where(Fighter.name == fighter_name)
    ).first()

    if not fighter:
        return False

    post = session.exec(
        select(InstagramPost)
        .join(Card, Card.id == InstagramPost.card_id)
        .where(Card.fighter_id == fighter.id)
        .limit(1)
    ).first()

    return post is not None


async def _run_pipeline(fighter_name: str) -> dict[str, Any]:
    """Run the full generate + post pipeline for a fighter name.

    Mirrors the logic in api.py /generate and /post routes but runs
    headlessly without a request context. Saves all DB records.

    Raises:
        Any pipeline exception (FetchError, EnrichmentError, etc.) — caller handles.
    """
    import json

    engine = get_engine()

    raw_data = await fetcher.get_fighter_data(fighter_name)
    enriched_data = await enricher.enrich_fighter(raw_data)
    card_paths = await renderer.render_carousel(enriched_data)
    caption = caption_builder.build_caption(enriched_data)

    with Session(engine) as session:
        # Upsert Fighter
        fighter = session.exec(
            select(Fighter).where(Fighter.name == enriched_data.get("name"))
        ).first()

        if fighter:
            fighter.nickname = enriched_data.get("nickname")
            fighter.nationality = enriched_data.get("nationality")
            fighter.gym = enriched_data.get("gym")
            fighter.record_wins = enriched_data.get("record_wins")
            fighter.record_losses = enriched_data.get("record_losses")
            fighter.record_kos = enriched_data.get("record_kos")
            fighter.record_draws = enriched_data.get("record_draws")
            fighter.wikipedia_url = raw_data.get("wikipedia_url")
            fighter.updated_at = datetime.now(UTC)
            session.add(fighter)
        else:
            fighter = Fighter(
                name=enriched_data.get("name"),
                nickname=enriched_data.get("nickname"),
                nationality=enriched_data.get("nationality"),
                gym=enriched_data.get("gym"),
                record_wins=enriched_data.get("record_wins"),
                record_losses=enriched_data.get("record_losses"),
                record_kos=enriched_data.get("record_kos"),
                record_draws=enriched_data.get("record_draws"),
                wikipedia_url=raw_data.get("wikipedia_url"),
            )
            session.add(fighter)

        session.commit()
        session.refresh(fighter)

        profile = FighterProfile(
            fighter_id=fighter.id,
            fighting_style=enriched_data.get("fighting_style", ""),
            signature_weapons=json.dumps(enriched_data.get("signature_weapons", [])),
            attr_aggression=enriched_data["attributes"]["aggression"],
            attr_power=enriched_data["attributes"]["power"],
            attr_footwork=enriched_data["attributes"]["footwork"],
            attr_clinch=enriched_data["attributes"]["clinch"],
            attr_cardio=enriched_data["attributes"]["cardio"],
            attr_technique=enriched_data["attributes"]["technique"],
            bio=enriched_data.get("bio", ""),
            fun_fact=enriched_data.get("fun_fact"),
            career_highlight=enriched_data.get("career_highlight"),
            hashtags=json.dumps(enriched_data.get("hashtags", [])),
            recent_results=json.dumps(enriched_data.get("recent_results", [])),
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)

        for card_path in card_paths:
            card = Card(
                fighter_id=fighter.id,
                profile_id=profile.id,
                local_path=str(card_path),
                caption=caption,
            )
            session.add(card)
        session.commit()

        # Upload + publish
        image_urls = await uploader.upload_carousel(card_paths)
        instagram_post_id = await publisher.post_carousel(image_urls, caption)

        # Save post records
        cards = session.exec(
            select(Card).where(Card.profile_id == profile.id)
        ).all()

        for i, card in enumerate(cards):
            card.r2_url = image_urls[i]
            session.add(card)
            post_record = InstagramPost(
                card_id=card.id,
                instagram_id=instagram_post_id,
                caption_used=caption,
            )
            session.add(post_record)

        session.commit()

    return {"fighter_name": fighter_name, "instagram_post_id": instagram_post_id}
