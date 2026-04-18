# Fighter Queue & Scheduler — Implementation Spec

## Overview

Add a fighter queue system and APScheduler-based scheduler to the Muay Thai Cards app.
The queue holds a list of fighters to be processed. The scheduler works through them one
at a time on a defined cadence. The existing manual UI flow is untouched — it continues
to work exactly as before. A new Queue tab is added to the UI alongside it.

---

## What "already posted" means

`InstagramPost` already exists in `models.py`. A fighter is considered posted if there is
at least one `InstagramPost` row linked (via `Card`) to their `Fighter` row. The scheduler
uses this to skip fighters that have already been posted rather than relying on queue
status alone. This prevents re-posting if the queue is ever re-seeded.

---

## Out of scope: re-posting a fighter who is already done

Resetting a `done` queue item back to `pending` will not cause the scheduler to re-run
the pipeline. The deduplication guard in `_has_been_posted()` checks `InstagramPost` and
will immediately mark it `done` again without posting.

Re-posting a fighter intentionally (updated card, new season, etc.) is a separate concern
from queue management. It belongs on a future **Fighters** view built on top of the
existing `GET /fighters` endpoint — a "Regenerate & Post" action per fighter row that
bypasses the queue entirely. This is not part of this spec.

The inline edit UI described in section 9 therefore intentionally excludes `done` from
the editable status values.

---

## 1. New dependency

Add `apscheduler` to the project:

```bash
uv add apscheduler
```

---

## 2. `server/models.py` — add `FighterQueue`

Add this model to the bottom of the file. Do not modify any existing models.

```python
class FighterQueue(SQLModel, table=True):
    """One row per fighter in the posting queue."""

    id: Optional[int] = Field(default=None, primary_key=True)
    fighter_name: str = Field(index=True)
    priority: int = Field(default=0)       # higher = processed sooner
    status: str = Field(default="pending") # pending | processing | done | failed
    error_message: Optional[str] = Field(default=None)
    added_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    processed_at: Optional[datetime] = Field(default=None)
```

---

## 3. `server/exceptions.py` — add `QueueError`

Add to the bottom of the file:

```python
class QueueError(Exception):
    """Raised when a queue operation fails."""
```

---

## 4. New file: `server/scheduler.py`

Create this file from scratch. It owns all scheduling logic.

```python
import logging
from datetime import datetime, UTC
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


def start_scheduler() -> None:
    """Start the scheduler with the queue job. Called once at app startup."""
    scheduler = get_scheduler()
    # Runs once per hour by default. Adjust cron args as needed.
    scheduler.add_job(
        process_next_queued_fighter,
        trigger="cron",
        hour="*",      # every hour — change to e.g. hour=9, minute=0 for once daily at 9am
        minute=0,
        id="queue_job",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started")


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
        logger.info("Queue: pipeline complete for %s — post ID %s", fighter_name, result["instagram_post_id"])

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
    from server.database import get_engine
    from server.models import Fighter, FighterProfile, Card, InstagramPost

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
```

---

## 5. `server/api.py` — changes

### 5a. Update imports

Replace the existing `from server.models import ...` and `from sqlmodel import ...` lines
with the following — extend them to include `FighterQueue` and `func`:

```python
from sqlmodel import Session, select, desc, func
from server.scheduler import get_scheduler, process_next_queued_fighter, start_scheduler, stop_scheduler
from server.models import Fighter, FighterProfile, Card, InstagramPost, FighterQueue
```

### 5b. Update the `lifespan` context manager

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database schema and start the scheduler on startup."""
    create_db_and_tables()
    logger.info("Database initialized")
    start_scheduler()
    yield
    stop_scheduler()
```

### 5c. Add queue request/response schemas

Add these alongside the existing Pydantic schemas:

```python
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
```

### 5d. Add queue endpoints

```python
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
    added = []
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
        session.commit()
        session.refresh(item)
        added.append(QueueItemResponse(**item.model_dump()))
    return added


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
```

---

## 6. `server/api.py` — add `/fighters/seed` endpoint

Add this route to serve the seed list to the frontend:

```python
import json as json_module

@app.get("/fighters/seed")
async def get_seed_fighters() -> list[str]:
    """Return the seed fighter list from data/fighters.json."""
    seed_path = Path("data/fighters.json")
    if not seed_path.exists():
        return []
    return json_module.loads(seed_path.read_text())
```

---

## 7. New file: `data/fighters.json`

Create this file. It is the seed list for bulk import.

```json
[
  "Rodtang Jitmuangnon",
  "Superlek Kiatmoo9",
  "Nong-O Hama",
  "Saenchai",
  "Buakaw Banchamek",
  "Sangmanee Sor Tienpo",
  "Petchmorakot Petchyindee",
  "Panpayak Jitmuangnon",
  "Liam Harrison",
  "Jonathan Haggerty",
  "Tawanchai PK Saenchai",
  "Superbon Singha Mawynn",
  "Giorgio Petrosyan",
  "Sitthichai Sitsongpeenong",
  "Smokin' Jo Nattawut",
  "Nico Carrillo",
  "Kongthoranee Sor Sommai",
  "Sinsamut Klinmee",
  "Yodsanklai Fairtex",
  "Namsaknoi Yudthagarngamtorn",
  "Attachai Fairtex",
  "Dzhabar Askerov",
  "Chingiz Allazov",
  "Tayfun Ozcan",
  "Enriko Kehl",
  "Marat Grigorian",
  "Samy Sana",
  "Davit Kiria",
  "Petchtanong Petchfergus",
  "Anuwat Kaewsamrit"
]
```

---

## 8. `ui/index.html` — add Queue tab

Replace the `<main class="app-main">` section entirely with the following.
The existing Generate flow is preserved inside the first tab unchanged.

```html
<main class="app-main">

  <!-- Tab navigation -->
  <nav class="tab-nav">
    <button class="tab-btn active" data-tab="generate">Generate</button>
    <button class="tab-btn" data-tab="queue">Queue</button>
  </nav>

  <!-- ── Generate Tab (existing content, unchanged) ── -->
  <div class="tab-panel active" id="tab-generate">

    <section class="input-section">
      <div class="input-group">
        <input
          type="text"
          id="fighter-input"
          class="fighter-input"
          placeholder="Enter fighter name e.g. Rodtang Jitmuangnon"
          autocomplete="off"
        />
        <button id="generate-btn" class="btn btn-primary">Generate Card</button>
      </div>
    </section>

    <section id="progress-section" class="progress-section hidden">
      <div class="progress-steps">
        <div class="step" id="step-scrape">
          <span class="step-icon">⬜</span>
          <span class="step-label">Scraping fighter data</span>
        </div>
        <div class="step" id="step-enrich">
          <span class="step-icon">⬜</span>
          <span class="step-label">Enriching with Claude AI</span>
        </div>
        <div class="step" id="step-render">
          <span class="step-icon">⬜</span>
          <span class="step-label">Rendering card</span>
        </div>
      </div>
    </section>

    <section id="preview-section" class="preview-section hidden">
      <div class="preview-container">
        <div class="carousel">
          <div class="carousel-track" id="carousel-track">
            <img class="carousel-slide" id="slide-1" src="" alt="Slide 1" />
            <img class="carousel-slide" id="slide-2" src="" alt="Slide 2" />
            <img class="carousel-slide" id="slide-3" src="" alt="Slide 3" />
          </div>
        </div>
        <div class="carousel-dots">
          <button class="dot active" data-index="0" aria-label="Slide 1"></button>
          <button class="dot" data-index="1" aria-label="Slide 2"></button>
          <button class="dot" data-index="2" aria-label="Slide 3"></button>
        </div>
      </div>

      <div class="caption-container">
        <label for="caption-input" class="caption-label">Instagram Caption</label>
        <textarea id="caption-input" class="caption-input" rows="4" placeholder="Caption will appear here..."></textarea>
      </div>

      <div class="actions">
        <button id="post-btn" class="btn btn-accent">Post to Instagram</button>
      </div>
    </section>

    <section id="status-section" class="status-section hidden">
      <div id="status-message" class="status-message"></div>
    </section>

  </div>

  <!-- ── Queue Tab ── -->
  <div class="tab-panel hidden" id="tab-queue">

    <!-- Status bar -->
    <section class="queue-status-bar" id="queue-status-bar">
      <span class="queue-stat" id="stat-pending">— pending</span>
      <span class="queue-stat" id="stat-done">— done</span>
      <span class="queue-stat" id="stat-failed">— failed</span>
      <span class="queue-scheduler" id="stat-scheduler">scheduler —</span>
    </section>

    <!-- Add single fighter -->
    <section class="input-section">
      <div class="input-group">
        <input
          type="text"
          id="queue-input"
          class="fighter-input"
          placeholder="Fighter name to add to queue"
          autocomplete="off"
        />
        <button id="queue-add-btn" class="btn btn-primary">Add to Queue</button>
      </div>
    </section>

    <!-- Bulk import -->
    <section class="bulk-section">
      <label for="bulk-input" class="caption-label">Bulk Import (one name per line)</label>
      <textarea
        id="bulk-input"
        class="caption-input"
        rows="5"
        placeholder="Rodtang Jitmuangnon&#10;Superlek Kiatmoo9&#10;Nong-O Hama"
      ></textarea>
      <div class="bulk-actions">
        <button id="bulk-add-btn" class="btn btn-primary">Import List</button>
        <button id="load-seed-btn" class="btn btn-secondary">Load Seed List</button>
      </div>
    </section>

    <!-- Manual run -->
    <section class="queue-actions">
      <button id="run-now-btn" class="btn btn-accent">▶ Run Next Now</button>
    </section>

    <!-- Queue status message -->
    <section id="queue-status-section" class="status-section hidden">
      <div id="queue-status-message" class="status-message"></div>
    </section>

    <!-- Queue list -->
    <section class="queue-list-section">
      <div id="queue-list" class="queue-list">
        <p class="queue-empty">Queue is empty. Add fighters above.</p>
      </div>
    </section>

  </div>

</main>
```

---

## 9. `ui/app.js` — append Queue tab logic

Append the following to the bottom of `app.js`. Do not modify any existing code above it.

Each queue item renders in two states:
- **View mode** — name, priority, status badge, edit button (pending + failed only), delete button (pending only)
- **Edit mode** — inline form with name input, priority number input, reset-to-pending checkbox (failed only), save and cancel buttons

```javascript
// ===========================================================================
// Queue Tab
// ===========================================================================

// --- Tab switching ---

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.remove('hidden');
    if (btn.dataset.tab === 'queue') {
      loadQueue();
      loadQueueStatus();
    }
  });
});

// --- DOM refs ---

const queueInput     = document.getElementById('queue-input');
const queueAddBtn    = document.getElementById('queue-add-btn');
const bulkInput      = document.getElementById('bulk-input');
const bulkAddBtn     = document.getElementById('bulk-add-btn');
const loadSeedBtn    = document.getElementById('load-seed-btn');
const runNowBtn      = document.getElementById('run-now-btn');
const queueList      = document.getElementById('queue-list');
const queueStatusMsg = document.getElementById('queue-status-message');
const queueStatusSec = document.getElementById('queue-status-section');
const statPending    = document.getElementById('stat-pending');
const statDone       = document.getElementById('stat-done');
const statFailed     = document.getElementById('stat-failed');
const statScheduler  = document.getElementById('stat-scheduler');

// --- Helpers ---

function showQueueStatus(message, type = 'success') {
  queueStatusMsg.textContent = message;
  queueStatusMsg.className = `status-message ${type}`;
  queueStatusSec.classList.remove('hidden');
  setTimeout(() => queueStatusSec.classList.add('hidden'), 4000);
}

function statusBadge(status) {
  const map = {
    pending:    { label: 'Pending',  cls: 'badge-pending' },
    processing: { label: 'Running…', cls: 'badge-processing' },
    done:       { label: 'Done',     cls: 'badge-done' },
    failed:     { label: 'Failed',   cls: 'badge-failed' },
  };
  const s = map[status] ?? { label: status, cls: '' };
  return `<span class="badge ${s.cls}">${s.label}</span>`;
}

// --- Render a single queue item ---
// pending: view row + edit row (name, priority)
// failed:  view row + edit row (name, priority, reset-to-pending checkbox)
// processing / done: view row only, no controls

function renderQueueItem(item) {
  const canEdit   = item.status === 'pending' || item.status === 'failed';
  const canDelete = item.status === 'pending';
  const canReset  = item.status === 'failed';

  return `
    <div class="queue-item" data-id="${item.id}" data-status="${item.status}">

      <!-- View row -->
      <div class="queue-view-row">
        <div class="queue-item-info">
          <span class="queue-fighter-name">${item.fighter_name}</span>
          <span class="queue-priority-label">priority ${item.priority}</span>
          ${item.error_message
            ? `<span class="queue-error" title="${item.error_message}">${item.error_message}</span>`
            : ''}
        </div>
        <div class="queue-item-meta">
          ${statusBadge(item.status)}
          ${canEdit   ? `<button class="btn-icon btn-edit"   data-id="${item.id}" title="Edit">✏️</button>` : ''}
          ${canDelete ? `<button class="btn-icon btn-remove" data-id="${item.id}" title="Remove">✕</button>` : ''}
        </div>
      </div>

      <!-- Edit row (hidden by default, shown on edit button click) -->
      ${canEdit ? `
      <div class="queue-edit-row hidden" id="edit-row-${item.id}">
        <div class="queue-edit-fields">
          <input
            type="text"
            class="edit-name-input fighter-input"
            data-id="${item.id}"
            value="${item.fighter_name}"
            placeholder="Fighter name"
          />
          <input
            type="number"
            class="edit-priority-input priority-input"
            data-id="${item.id}"
            value="${item.priority}"
            min="0"
            max="100"
            title="Priority (higher = sooner)"
          />
        </div>
        ${canReset ? `
        <label class="reset-label">
          <input type="checkbox" class="reset-checkbox" data-id="${item.id}" />
          Reset to pending (retry this fighter)
        </label>` : ''}
        <div class="queue-edit-actions">
          <button class="btn btn-primary btn-save"   data-id="${item.id}">Save</button>
          <button class="btn btn-secondary btn-cancel" data-id="${item.id}">Cancel</button>
        </div>
      </div>` : ''}

    </div>
  `;
}

// --- Load queue list ---

async function loadQueue() {
  try {
    const res = await fetch('/queue');
    const items = await res.json();

    if (!items.length) {
      queueList.innerHTML = '<p class="queue-empty">Queue is empty. Add fighters above.</p>';
      return;
    }

    queueList.innerHTML = items.map(renderQueueItem).join('');
    attachQueueListeners();

  } catch {
    showQueueStatus('Failed to load queue.', 'error');
  }
}

// --- Attach listeners to rendered queue rows ---

function attachQueueListeners() {

  // Edit button — toggle edit row
  queueList.querySelectorAll('.btn-edit').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById(`edit-row-${btn.dataset.id}`).classList.toggle('hidden');
    });
  });

  // Cancel button — close edit row
  queueList.querySelectorAll('.btn-cancel').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById(`edit-row-${btn.dataset.id}`).classList.add('hidden');
    });
  });

  // Save button — PATCH the item
  queueList.querySelectorAll('.btn-save').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      const nameInput     = queueList.querySelector(`.edit-name-input[data-id="${id}"]`);
      const priorityInput = queueList.querySelector(`.edit-priority-input[data-id="${id}"]`);
      const resetCheckbox = queueList.querySelector(`.reset-checkbox[data-id="${id}"]`);

      const payload = {};
      if (nameInput?.value.trim())          payload.fighter_name = nameInput.value.trim();
      if (priorityInput)                    payload.priority = Number(priorityInput.value);
      if (resetCheckbox?.checked)           payload.status = 'pending';

      try {
        const res = await fetch(`/queue/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const err = await res.json();
          showQueueStatus(err.detail || 'Update failed.', 'error');
          return;
        }

        showQueueStatus('Queue item updated.');
        loadQueue();
        loadQueueStatus();

      } catch {
        showQueueStatus('Network error.', 'error');
      }
    });
  });

  // Remove button — DELETE the item
  queueList.querySelectorAll('.btn-remove').forEach(btn => {
    btn.addEventListener('click', () => removeFromQueue(Number(btn.dataset.id)));
  });
}

// --- Load queue status bar ---

async function loadQueueStatus() {
  try {
    const res = await fetch('/queue/status');
    const data = await res.json();
    statPending.textContent   = `${data.counts.pending} pending`;
    statDone.textContent      = `${data.counts.done} done`;
    statFailed.textContent    = `${data.counts.failed} failed`;
    statScheduler.textContent = `scheduler ${data.scheduler_running ? '🟢 on' : '🔴 off'}`;
  } catch {
    statScheduler.textContent = 'scheduler —';
  }
}

// --- Add single fighter ---

queueAddBtn.addEventListener('click', async () => {
  const name = queueInput.value.trim();
  if (!name) return;

  try {
    const res = await fetch('/queue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fighter_name: name }),
    });

    if (!res.ok) {
      const err = await res.json();
      showQueueStatus(err.detail || 'Failed to add fighter.', 'error');
      return;
    }

    queueInput.value = '';
    showQueueStatus(`${name} added to queue.`);
    loadQueue();
    loadQueueStatus();
  } catch {
    showQueueStatus('Network error.', 'error');
  }
});

queueInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') queueAddBtn.click();
});

// --- Bulk import ---

bulkAddBtn.addEventListener('click', async () => {
  const raw = bulkInput.value.trim();
  if (!raw) return;

  const names = raw.split('\n').map(n => n.trim()).filter(Boolean);
  if (!names.length) return;

  try {
    const res = await fetch('/queue/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fighter_names: names }),
    });

    const added = await res.json();
    bulkInput.value = '';
    showQueueStatus(`${added.length} fighter(s) added to queue.`);
    loadQueue();
    loadQueueStatus();
  } catch {
    showQueueStatus('Network error.', 'error');
  }
});

// --- Load seed list into bulk textarea ---

loadSeedBtn.addEventListener('click', async () => {
  try {
    const res = await fetch('/fighters/seed');
    const names = await res.json();
    bulkInput.value = names.join('\n');
    showQueueStatus('Seed list loaded. Click Import List to add them.', 'success');
  } catch {
    showQueueStatus('Could not load seed list.', 'error');
  }
});

// --- Remove from queue ---

async function removeFromQueue(id) {
  try {
    const res = await fetch(`/queue/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      showQueueStatus(err.detail || 'Could not remove.', 'error');
      return;
    }
    loadQueue();
    loadQueueStatus();
  } catch {
    showQueueStatus('Network error.', 'error');
  }
}

// --- Run next now ---

runNowBtn.addEventListener('click', async () => {
  runNowBtn.disabled = true;
  runNowBtn.textContent = '⏳ Running…';

  try {
    const res = await fetch('/queue/run-now', { method: 'POST' });
    const data = await res.json();

    if (data.status === 'empty') {
      showQueueStatus('Queue is empty — nothing to run.', 'error');
    } else {
      showQueueStatus(`Posted: ${data.fighter_name} — Instagram ID: ${data.instagram_post_id}`);
    }

    loadQueue();
    loadQueueStatus();
  } catch {
    showQueueStatus('Network error.', 'error');
  } finally {
    runNowBtn.disabled = false;
    runNowBtn.textContent = '▶ Run Next Now';
  }
});
```

---

## 10. `ui/styles.css` — append queue styles

Append to the bottom of `styles.css`:

```css
/* ============================================================
   Tabs
   ============================================================ */
.tab-nav {
  display: flex;
  gap: 4px;
  margin-bottom: 32px;
  border-bottom: 1px solid var(--border);
  width: 100%;
  max-width: 640px;
}

.tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: 0.95rem;
  letter-spacing: 0.05em;
  padding: 10px 20px;
  text-transform: uppercase;
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn.active,
.tab-btn:hover {
  border-bottom-color: var(--accent-red);
  color: var(--text-primary);
}

.tab-panel {
  width: 100%;
  max-width: 640px;
}

/* ============================================================
   Queue status bar
   ============================================================ */
.queue-status-bar {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 24px;
  font-family: var(--font-ui);
  font-size: 0.85rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.queue-scheduler {
  margin-left: auto;
}

/* ============================================================
   Bulk import
   ============================================================ */
.bulk-section {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bulk-actions {
  display: flex;
  gap: 8px;
}

.btn-secondary {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: 0.9rem;
  letter-spacing: 0.05em;
  padding: 10px 20px;
  border-radius: var(--radius);
  text-transform: uppercase;
  transition: border-color 0.15s, color 0.15s;
}

.btn-secondary:hover {
  border-color: var(--text-secondary);
  color: var(--text-primary);
}

/* ============================================================
   Queue actions (run now)
   ============================================================ */
.queue-actions {
  margin-top: 24px;
  display: flex;
  gap: 8px;
}

/* ============================================================
   Queue list
   ============================================================ */
.queue-list-section {
  margin-top: 32px;
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.queue-empty {
  color: var(--text-muted);
  font-size: 0.9rem;
  text-align: center;
  padding: 24px 0;
}

/* ============================================================
   Queue item — view row
   ============================================================ */
.queue-item {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.queue-view-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
}

.queue-item-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.queue-fighter-name {
  font-family: var(--font-ui);
  font-size: 0.95rem;
  letter-spacing: 0.03em;
  color: var(--text-primary);
}

.queue-priority-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.queue-error {
  font-size: 0.78rem;
  color: var(--accent-red);
  max-width: 380px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.queue-item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ============================================================
   Queue item — edit row
   ============================================================ */
.queue-edit-row {
  border-top: 1px solid var(--border);
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--bg-elevated);
}

.queue-edit-fields {
  display: flex;
  gap: 8px;
}

.priority-input {
  width: 72px;
  background: var(--input-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: 0.9rem;
  padding: 8px 10px;
  text-align: center;
}

.priority-input:focus {
  border-color: var(--accent-red);
  outline: none;
}

.reset-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: var(--text-secondary);
  cursor: pointer;
}

.reset-checkbox {
  accent-color: var(--accent-red);
  width: 14px;
  height: 14px;
}

.queue-edit-actions {
  display: flex;
  gap: 8px;
}

/* ============================================================
   Badges
   ============================================================ */
.badge {
  border-radius: 4px;
  font-family: var(--font-ui);
  font-size: 0.72rem;
  letter-spacing: 0.07em;
  padding: 3px 8px;
  text-transform: uppercase;
}

.badge-pending    { background: #2a2a1a; color: #ccaa44; }
.badge-processing { background: #1a2a3a; color: #4499cc; }
.badge-done       { background: #1a2a1a; color: #44cc66; }
.badge-failed     { background: #2a1a1a; color: var(--accent-red); }

/* ============================================================
   Icon buttons (edit / remove)
   ============================================================ */
.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  line-height: 1;
  padding: 4px 6px;
  border-radius: var(--radius);
  opacity: 0.5;
  transition: opacity 0.15s;
}

.btn-icon:hover {
  opacity: 1;
}

.btn-remove:hover {
  color: var(--accent-red);
}
```

---

## Summary of files changed

| File | Change |
|---|---|
| `server/models.py` | Add `FighterQueue` model |
| `server/exceptions.py` | Add `QueueError` |
| `server/scheduler.py` | **New file** — scheduler + headless pipeline runner |
| `server/api.py` | Update imports + lifespan, add `QueueUpdateRequest` schema, add 7 endpoints |
| `ui/index.html` | Add tab nav, wrap existing content in Generate tab, add Queue tab |
| `ui/app.js` | Append tab switching + full queue UI logic with inline edit rows |
| `ui/styles.css` | Append tab, queue, edit row, badge, icon button styles |
| `data/fighters.json` | **New file** — 30-fighter seed list |

---

## Notes for Claude Code

- Run `uv add apscheduler` before anything else
- The scheduler fires hourly by default. To change the cadence, edit `start_scheduler()`
  in `scheduler.py` — the `cron` trigger args are standard APScheduler kwargs
- `PATCH /queue/{id}` accepts `fighter_name`, `priority`, and `status`. The only valid
  `status` value is `"pending"`, and only when the current status is `"failed"`. The
  route enforces this explicitly — do not relax these guards
- Items with status `processing` or `done` are fully locked — the PATCH route rejects
  edits to both, and the UI only renders edit/delete controls for `pending` and `failed`
- The delete route only accepts `pending` items — enforced in both API and UI
- `_has_been_posted()` in `scheduler.py` is the deduplication guard. It checks
  `InstagramPost` linked via `Card` to `Fighter`. This runs before every pipeline
  execution so re-seeding the queue never causes a double-post
- `func.count` requires `from sqlmodel import func` in `api.py` imports
- The "Load Seed List" button calls `GET /fighters/seed` — this endpoint must exist in
  `api.py` before the UI can use it
- **Future work — re-posting a done fighter:** belongs on a Fighters view built on top
  of the existing `GET /fighters` endpoint. A "Regenerate & Post" button per fighter row
  is the correct pattern — it bypasses the queue and the dedup guard entirely. This is
  explicitly out of scope for this spec.
