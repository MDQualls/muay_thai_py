import json
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select, desc

from server import pipeline
from server.database import create_session
from server.exceptions import EnrichmentError, FetchError, PublishError, RenderError, UploadError
from server.models import Card, Fighter, FighterQueue, InstagramPost

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
        except JobLookupError:
            logger.debug("Scheduler job 'queue_job' did not exist — nothing to remove")


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
    with create_session() as session:
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
        result = await pipeline.run_full_pipeline(fighter_name)
        logger.info(
            "Queue: pipeline complete for %s — post ID %s",
            fighter_name,
            result["instagram_post_id"],
        )

        with create_session() as session:
            item = session.get(FighterQueue, queue_id)
            if item is None:
                logger.warning("Queue item %d disappeared after pipeline — cannot mark done", queue_id)
                return result
            item.status = "done"
            item.processed_at = datetime.now(UTC)
            session.add(item)
            session.commit()

        return result

    except (FetchError, EnrichmentError, RenderError, UploadError, PublishError) as e:
        logger.error("Queue: pipeline failed for %s: %s", fighter_name, e)
        with create_session() as session:
            item = session.get(FighterQueue, queue_id)
            if item is None:
                logger.warning("Queue item %d disappeared after pipeline failure — cannot mark failed", queue_id)
                return None
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
