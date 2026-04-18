import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, UTC
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import Session, select, desc, func
from server.models import Fighter, FighterProfile, Card, InstagramPost, FighterQueue

from server import enricher, fetcher, publisher, renderer, uploader, caption_builder, pipeline
from server.database import create_db_and_tables, get_session
from server.exceptions import EnrichmentError, FetchError, PublishError, RenderError, UploadError
from server.scheduler import (
    get_scheduler,
    process_next_queued_fighter,
    start_scheduler,
    stop_scheduler,
    apply_scheduler_config,
    load_scheduler_config,
)

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database schema and start the scheduler on startup."""
    create_db_and_tables()
    logger.info("Database initialized")
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Muay Thai Fighter Card App", lifespan=lifespan)

# Serve static files (JS, CSS) from the ui/ directory
app.mount("/static", StaticFiles(directory="ui"), name="static")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    fighter_name: str


class GenerateResponse(BaseModel):
    status: str
    card_paths: list[str]
    caption: str


class PostRequest(BaseModel):
    caption: str | None = None


class PostResponse(BaseModel):
    status: str
    instagram_post_id: str


class QueueAddRequest(BaseModel):
    fighter_name: str
    priority: int = 0


class QueueBulkAddRequest(BaseModel):
    fighter_names: list[str]
    priority: int = 0


class QueueUpdateRequest(BaseModel):
    """All fields optional — only provided fields are updated.

    status may only be set to 'pending'. This is intentionally limited:
    - 'pending' resets a failed item so the scheduler retries it
    - 'done' cannot be set here — re-posting a completed fighter is a separate
      concern handled by a future Regenerate action on the Fighters view
    - 'processing' and 'failed' are set exclusively by the scheduler
    """
    fighter_name: str | None = None
    priority: int | None = None
    status: str | None = None  # only "pending" accepted — validated in the route handler


class QueueItemResponse(BaseModel):
    id: int
    fighter_name: str
    priority: int
    status: str
    error_message: str | None
    added_at: datetime
    processed_at: datetime | None


class QueueRunResponse(BaseModel):
    status: str
    detail: str
    fighter_name: str | None = None
    instagram_post_id: str | None = None


class SchedulerConfigRequest(BaseModel):
    """Scheduler settings submitted from the UI.

    days: list of APScheduler day-of-week abbreviations from the set
          ["sun", "mon", "tue", "wed", "thu", "fri", "sat"].
          At least one day required when enabled is True.
    time: wall-clock time in HH:MM 24-hour format e.g. "09:00", "18:30".
    timezone: IANA timezone name from the browser e.g. "America/Chicago".
              Ensures the cron job fires at the user's local wall-clock time,
              not UTC. Sent automatically by the frontend on every save.
    enabled: when False the scheduler job is removed and no posts run on schedule.
    """
    enabled: bool
    days: list[str]
    time: str  # HH:MM 24-hour
    timezone: str = "UTC"  # IANA timezone name


class SchedulerConfigResponse(BaseModel):
    enabled: bool
    days: list[str]
    time: str
    timezone: str
    scheduler_running: bool
    next_run: str | None  # ISO 8601 datetime string, or None if no job is scheduled


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
async def index() -> FileResponse:
    """Serve the frontend SPA."""
    return FileResponse("ui/index.html")


@app.post("/generate", response_model=GenerateResponse)
async def generate(
    request: GenerateRequest,
    session: Session = Depends(get_session),
) -> GenerateResponse:
    """Run the full fighter card pipeline: scrape → enrich → render."""
    try:
        logger.info("Generating card for fighter: %s", request.fighter_name)

        raw_data = await fetcher.get_fighter_data(request.fighter_name)
        enriched_data = await enricher.enrich_fighter(raw_data)
        card_paths = await renderer.render_carousel(enriched_data)
        caption = caption_builder.build_caption(enriched_data)

        pipeline.save_generation(session, raw_data, enriched_data, card_paths, caption)

        return GenerateResponse(
            status="ok",
            card_paths=[str(p) for p in card_paths],
            caption=caption,
        )
    except FetchError as e:
        logger.error("Data fetch failed for %s: %s", request.fighter_name, e)
        raise HTTPException(status_code=502, detail=str(e))
    except EnrichmentError as e:
        logger.error("Enrichment failed for %s: %s", request.fighter_name, e)
        raise HTTPException(status_code=502, detail=str(e))
    except RenderError as e:
        logger.error("Render failed for %s: %s", request.fighter_name, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/preview")
async def preview(slide: int = 1, session: Session = Depends(get_session)) -> FileResponse:
    """Return a slide from the most recently generated carousel.

    Args:
        slide: Slide number 1–3. Defaults to 1.
    """
    latest_card = session.exec(
        select(Card).order_by(desc(Card.created_at))
    ).first()

    if not latest_card:
        raise HTTPException(status_code=404, detail="No card generated yet")

    # Get all slides from the same generation run, ordered by filename (slide1, slide2, slide3)
    cards = session.exec(
        select(Card)
        .where(Card.profile_id == latest_card.profile_id)
        .order_by(Card.local_path)
    ).all()

    slide_index = max(0, min(slide - 1, len(cards) - 1))
    card_path = Path(cards[slide_index].local_path)

    if not card_path.exists():
        raise HTTPException(status_code=404, detail="Card file not found on disk")

    return FileResponse(str(card_path), media_type="image/jpeg")


@app.post("/post", response_model=PostResponse)
async def post(
    request: PostRequest,
    session: Session = Depends(get_session),
) -> PostResponse:
    """Upload the latest card to R2 and post it to Instagram."""
    try:
        latest_card = session.exec(
            select(Card).order_by(desc(Card.created_at))
        ).first()

        if not latest_card:
            raise HTTPException(status_code=400, detail="No cards generated yet.")

        # Guard against double-posting the same set of cards
        existing_post = session.exec(
            select(InstagramPost).where(InstagramPost.card_id == latest_card.id).limit(1)
        ).first()
        if existing_post:
            raise HTTPException(
                status_code=409,
                detail="These cards have already been posted to Instagram.",
            )

        cards = session.exec(
            select(Card).where(Card.profile_id == latest_card.profile_id)
        ).all()

        card_paths = [Path(card.local_path) for card in cards]
        caption = request.caption or latest_card.caption or ""
        image_urls = await uploader.upload_carousel(card_paths)
        instagram_post_id = await publisher.post_carousel(image_urls, caption)

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

        return PostResponse(status="posted", instagram_post_id=instagram_post_id)
    except UploadError as e:
        logger.error("Upload failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except PublishError as e:
        logger.error("Instagram publish failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/fighters")
async def list_fighters(
    session: Session = Depends(get_session),
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return fighters from the database, paginated."""
    fighters = session.exec(select(Fighter).offset(offset).limit(limit)).all()
    return [f.model_dump() for f in fighters]


@app.get("/fighters/{fighter_id}/cards")
async def get_fighter_cards(
    fighter_id: int,
    session: Session = Depends(get_session),
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return cards for a given fighter, including R2 URL and post status."""
    cards = session.exec(
        select(Card).where(Card.fighter_id == fighter_id).offset(offset).limit(limit)
    ).all()
    return [c.model_dump() for c in cards]


@app.get("/fighters/seed")
async def get_seed_fighters() -> list[str]:
    """Return the seed fighter list from data/fighters.json."""
    seed_path = Path("data/fighters.json")
    if not seed_path.exists():
        return []
    return json.loads(seed_path.read_text())


@app.get("/queue", response_model=list[QueueItemResponse])
async def list_queue(session: Session = Depends(get_session)) -> list[QueueItemResponse]:
    """Return all queue items ordered by priority desc, then added_at asc."""
    items = session.exec(
        select(FighterQueue)
        .order_by(desc(FighterQueue.priority), FighterQueue.added_at)
    ).all()
    return [QueueItemResponse(**item.model_dump()) for item in items]


@app.post("/queue", response_model=QueueItemResponse)
async def add_to_queue(
    request: QueueAddRequest,
    session: Session = Depends(get_session),
) -> QueueItemResponse:
    """Add a single fighter to the queue. Rejects duplicates with pending status."""
    existing = session.exec(
        select(FighterQueue)
        .where(FighterQueue.fighter_name == request.fighter_name)
        .where(FighterQueue.status == "pending")
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail=f"{request.fighter_name} is already in the queue.")

    item = FighterQueue(fighter_name=request.fighter_name, priority=request.priority)
    session.add(item)
    session.commit()
    session.refresh(item)
    return QueueItemResponse(**item.model_dump())


@app.post("/queue/bulk", response_model=list[QueueItemResponse])
async def bulk_add_to_queue(
    request: QueueBulkAddRequest,
    session: Session = Depends(get_session),
) -> list[QueueItemResponse]:
    """Add multiple fighters to the queue. Silently skips names already pending."""
    to_add = []
    for name in request.fighter_names:
        name = name.strip()
        if not name:
            continue
        existing = session.exec(
            select(FighterQueue)
            .where(FighterQueue.fighter_name == name)
            .where(FighterQueue.status == "pending")
        ).first()
        if existing:
            continue
        item = FighterQueue(fighter_name=name, priority=request.priority)
        session.add(item)
        to_add.append(item)

    session.commit()
    for item in to_add:
        session.refresh(item)
    return [QueueItemResponse(**item.model_dump()) for item in to_add]


@app.patch("/queue/{queue_id}", response_model=QueueItemResponse)
async def update_queue_item(
    queue_id: int,
    request: QueueUpdateRequest,
    session: Session = Depends(get_session),
) -> QueueItemResponse:
    """Update a queue item's name, priority, or reset a failed item to pending.

    Allowed status transitions via this endpoint:
      failed → pending  (retry)

    Items with status 'processing' or 'done' cannot be edited.
    """
    item = session.get(FighterQueue, queue_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found.")

    if item.status in ("processing", "done"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit an item with status '{item.status}'.",
        )

    if request.status is not None:
        if request.status != "pending":
            raise HTTPException(
                status_code=400,
                detail="Status can only be set to 'pending' via this endpoint.",
            )
        if item.status != "failed":
            raise HTTPException(
                status_code=400,
                detail="Only failed items can be reset to pending.",
            )
        item.status = "pending"
        item.error_message = None
        item.processed_at = None

    if request.fighter_name is not None:
        item.fighter_name = request.fighter_name.strip()

    if request.priority is not None:
        item.priority = request.priority

    session.add(item)
    session.commit()
    session.refresh(item)
    return QueueItemResponse(**item.model_dump())


@app.delete("/queue/{queue_id}")
async def remove_from_queue(
    queue_id: int,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Remove a fighter from the queue. Only pending items can be deleted."""
    item = session.get(FighterQueue, queue_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    if item.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot delete item with status '{item.status}'.")
    session.delete(item)
    session.commit()
    return {"status": "deleted"}


@app.post("/queue/run-now", response_model=QueueRunResponse)
async def run_queue_now() -> QueueRunResponse:
    """Manually trigger the next queued fighter to run immediately."""
    result = await process_next_queued_fighter()
    if result is None:
        return QueueRunResponse(status="empty", detail="No pending fighters in the queue.")
    return QueueRunResponse(
        status="ok",
        detail="Pipeline completed successfully.",
        fighter_name=result["fighter_name"],
        instagram_post_id=result["instagram_post_id"],
    )


@app.get("/queue/status")
async def queue_status(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Return counts by status and scheduler running state."""
    counts = {}
    for status in ("pending", "processing", "done", "failed"):
        count = session.exec(
            select(func.count(FighterQueue.id)).where(FighterQueue.status == status)
        ).one()
        counts[status] = count

    scheduler = get_scheduler()
    return {
        "counts": counts,
        "scheduler_running": scheduler.running,
    }


@app.get("/scheduler/config", response_model=SchedulerConfigResponse)
async def get_scheduler_config() -> SchedulerConfigResponse:
    """Return the current scheduler config and next scheduled run time."""
    config = load_scheduler_config()
    scheduler = get_scheduler()

    next_run = None
    try:
        job = scheduler.get_job("queue_job")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
    except Exception as e:
        logger.warning("Could not read scheduler job next_run_time: %s", e)

    return SchedulerConfigResponse(
        enabled=config.get("enabled", True),
        days=config.get("days", []),
        time=config.get("time", "09:00"),
        timezone=config.get("timezone", "UTC"),
        scheduler_running=scheduler.running,
        next_run=next_run,
    )


@app.post("/scheduler/config", response_model=SchedulerConfigResponse)
async def update_scheduler_config(
    request: SchedulerConfigRequest,
) -> SchedulerConfigResponse:
    """Save scheduler settings and apply them to the running scheduler immediately.

    Validation:
    - time must be HH:MM 24-hour format
    - days must only contain valid abbreviations: sun mon tue wed thu fri sat
    - if enabled is True, at least one day must be selected
    """
    valid_days = {"sun", "mon", "tue", "wed", "thu", "fri", "sat"}
    invalid = [d for d in request.days if d not in valid_days]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid day abbreviations: {invalid}. Must be from: sun mon tue wed thu fri sat",
        )

    try:
        hour, minute = request.time.split(":")
        if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail="time must be HH:MM in 24-hour format e.g. '09:00' or '18:30'.",
        )

    if request.enabled and not request.days:
        raise HTTPException(
            status_code=400,
            detail="At least one day must be selected when the scheduler is enabled.",
        )

    config = {
        "enabled": request.enabled,
        "days": request.days,
        "time": request.time,
        "timezone": request.timezone,
    }
    apply_scheduler_config(config)

    scheduler = get_scheduler()
    next_run = None
    try:
        job = scheduler.get_job("queue_job")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
    except Exception as e:
        logger.warning("Could not read scheduler job next_run_time: %s", e)

    return SchedulerConfigResponse(
        enabled=request.enabled,
        days=request.days,
        time=request.time,
        timezone=request.timezone,
        scheduler_running=scheduler.running,
        next_run=next_run,
    )
