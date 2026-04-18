# Scheduler Configuration — Implementation Spec

## Context

The queue and scheduler have already been built. `server/scheduler.py` exists but
`start_scheduler()` is hardcoded to fire every hour. There is no way to configure
the schedule from the UI. This spec adds that capability.

Do not rebuild anything that already exists. This spec only describes what needs
to be added or modified on top of the working codebase.

---

## What this adds

- `scheduler.py` — replace `start_scheduler()` with config-aware version, add four
  new functions: `load_scheduler_config()`, `save_scheduler_config()`,
  `_build_cron_kwargs()`, `apply_scheduler_config()`
- `api.py` — two new schemas (`SchedulerConfigRequest`, `SchedulerConfigResponse`)
  and two new endpoints (`GET /scheduler/config`, `POST /scheduler/config`),
  updated scheduler import line
- `ui/index.html` — scheduler settings panel added to the Queue tab, between the
  queue status message section and the queue list section
- `ui/app.js` — scheduler settings UI logic appended, tab-switch handler updated
  to call `loadSchedulerConfig()` alongside existing `loadQueue()` / `loadQueueStatus()`
- `ui/styles.css` — scheduler panel styles appended
- `data/scheduler_config.json` — auto-created on first save, not created manually

---

## 1. `server/scheduler.py` — modifications

Add `import json` and `from pathlib import Path` to the existing imports at the top
of the file.

Then **replace** the existing `start_scheduler()` function with the following five
functions. Everything else in the file stays exactly as-is.

```python
def load_scheduler_config() -> dict:
    """Load scheduler config from data/scheduler_config.json.

    Returns defaults if the file does not exist or is malformed.
    Default: enabled, runs Mon–Fri at 09:00.
    """
    defaults = {
        "enabled": True,
        "days": ["mon", "tue", "wed", "thu", "fri"],
        "time": "09:00",
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
        config: dict with keys 'days' (list of APScheduler day abbreviations)
                and 'time' (HH:MM 24-hour string)

    Returns:
        dict of kwargs for scheduler.add_job(trigger='cron', **kwargs)
    """
    hour, minute = config["time"].split(":")
    day_of_week = ",".join(config["days"])  # e.g. "mon,wed,fri"
    return {"hour": int(hour), "minute": int(minute), "day_of_week": day_of_week}


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
```

---

## 2. `server/api.py` — modifications

### 2a. Update the scheduler import line

The existing import line is:

```python
from server.scheduler import get_scheduler, process_next_queued_fighter, start_scheduler, stop_scheduler
```

Replace it with:

```python
from server.scheduler import (
    get_scheduler,
    process_next_queued_fighter,
    start_scheduler,
    stop_scheduler,
    apply_scheduler_config,
    load_scheduler_config,
)
```

### 2b. Add two new Pydantic schemas

Add these alongside the existing queue schemas (`QueueAddRequest`, `QueueItemResponse`, etc.):

```python
class SchedulerConfigRequest(BaseModel):
    """Scheduler settings submitted from the UI.

    days: list of APScheduler day-of-week abbreviations from the set
          ["sun", "mon", "tue", "wed", "thu", "fri", "sat"].
          At least one day required when enabled is True.
    time: wall-clock time in HH:MM 24-hour format e.g. "09:00", "18:30".
    enabled: when False the scheduler job is removed and no posts run on schedule.
    """
    enabled: bool
    days: list[str]
    time: str  # HH:MM 24-hour


class SchedulerConfigResponse(BaseModel):
    enabled: bool
    days: list[str]
    time: str
    scheduler_running: bool
    next_run: str | None  # ISO 8601 datetime string, or None if no job is scheduled
```

### 2c. Add two new endpoints

Add these after the existing `GET /queue/status` endpoint:

```python
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
    except Exception:
        pass

    return SchedulerConfigResponse(
        enabled=config.get("enabled", True),
        days=config.get("days", []),
        time=config.get("time", "09:00"),
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
    }
    apply_scheduler_config(config)

    scheduler = get_scheduler()
    next_run = None
    try:
        job = scheduler.get_job("queue_job")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
    except Exception:
        pass

    return SchedulerConfigResponse(
        enabled=request.enabled,
        days=request.days,
        time=request.time,
        scheduler_running=scheduler.running,
        next_run=next_run,
    )
```

---

## 3. `ui/index.html` — add scheduler settings panel

Inside the Queue tab (`<div class="tab-panel hidden" id="tab-queue">`), locate this
existing comment and section:

```html
        <!-- Queue status message -->
        <section id="queue-status-section" class="status-section hidden">
          <div id="queue-status-message" class="status-message"></div>
        </section>

        <!-- Queue list -->
```

Insert the scheduler settings panel between them, so it reads:

```html
        <!-- Queue status message -->
        <section id="queue-status-section" class="status-section hidden">
          <div id="queue-status-message" class="status-message"></div>
        </section>

        <!-- Scheduler settings -->
        <section class="scheduler-settings" id="scheduler-settings">
          <div class="scheduler-header">
            <span class="scheduler-title">Scheduler</span>
            <label class="toggle-label">
              <input type="checkbox" id="scheduler-enabled" />
              <span class="toggle-track">
                <span class="toggle-thumb"></span>
              </span>
              <span class="toggle-text" id="toggle-text">Enabled</span>
            </label>
          </div>

          <div class="scheduler-body" id="scheduler-body">
            <div class="day-picker">
              <span class="day-picker-label">Run on</span>
              <div class="day-pills">
                <label class="day-pill"><input type="checkbox" value="sun" /><span>Sun</span></label>
                <label class="day-pill"><input type="checkbox" value="mon" /><span>Mon</span></label>
                <label class="day-pill"><input type="checkbox" value="tue" /><span>Tue</span></label>
                <label class="day-pill"><input type="checkbox" value="wed" /><span>Wed</span></label>
                <label class="day-pill"><input type="checkbox" value="thu" /><span>Thu</span></label>
                <label class="day-pill"><input type="checkbox" value="fri" /><span>Fri</span></label>
                <label class="day-pill"><input type="checkbox" value="sat" /><span>Sat</span></label>
              </div>
            </div>

            <div class="time-picker-row">
              <span class="day-picker-label">At</span>
              <input type="time" id="scheduler-time" class="time-input" value="09:00" />
              <span class="time-hint" id="next-run-hint"></span>
            </div>

            <div class="scheduler-save-row">
              <button id="scheduler-save-btn" class="btn btn-primary">Save Schedule</button>
            </div>
          </div>
        </section>

        <!-- Queue list -->
```

---

## 4. `ui/app.js` — add scheduler settings logic

### 4a. Update the tab-switch handler

The existing tab-switch handler in the Queue Tab section reads:

```javascript
    if (btn.dataset.tab === 'queue') {
      loadQueue();
      loadQueueStatus();
    }
```

Update it to also call `loadSchedulerConfig()`:

```javascript
    if (btn.dataset.tab === 'queue') {
      loadQueue();
      loadQueueStatus();
      loadSchedulerConfig();
    }
```

### 4b. Append scheduler UI logic

Append the following block to the bottom of `app.js`, after the existing
`// --- Run next now ---` section:

```javascript
// --- Scheduler settings ---

const schedulerEnabled = document.getElementById('scheduler-enabled');
const toggleText       = document.getElementById('toggle-text');
const schedulerBody    = document.getElementById('scheduler-body');
const schedulerTime    = document.getElementById('scheduler-time');
const schedulerSaveBtn = document.getElementById('scheduler-save-btn');
const nextRunHint      = document.getElementById('next-run-hint');

async function loadSchedulerConfig() {
  try {
    const res  = await fetch('/scheduler/config');
    const data = await res.json();

    schedulerEnabled.checked = data.enabled;
    toggleText.textContent   = data.enabled ? 'Enabled' : 'Disabled';
    schedulerBody.classList.toggle('scheduler-body--disabled', !data.enabled);
    schedulerTime.value = data.time || '09:00';

    // Tick the correct day pills
    document.querySelectorAll('.day-pill input[type="checkbox"]').forEach(cb => {
      cb.checked = (data.days || []).includes(cb.value);
      // Sync the visual checked state via the sibling <span>
      cb.closest('.day-pill').classList.toggle('day-pill--active', cb.checked);
    });

    if (data.next_run) {
      const d = new Date(data.next_run);
      nextRunHint.textContent = `Next run: ${d.toLocaleString()}`;
    } else {
      nextRunHint.textContent = data.enabled ? '' : 'Scheduler disabled';
    }

  } catch {
    showQueueStatus('Could not load scheduler config.', 'error');
  }
}

// Toggle enabled/disabled — dims the body when off
schedulerEnabled.addEventListener('change', () => {
  const on = schedulerEnabled.checked;
  toggleText.textContent = on ? 'Enabled' : 'Disabled';
  schedulerBody.classList.toggle('scheduler-body--disabled', !on);
});

// Save schedule
schedulerSaveBtn.addEventListener('click', async () => {
  const enabled = schedulerEnabled.checked;
  const days    = [...document.querySelectorAll('.day-pill input:checked')].map(cb => cb.value);
  const time    = schedulerTime.value;

  if (enabled && !days.length) {
    showQueueStatus('Select at least one day before saving.', 'error');
    return;
  }

  schedulerSaveBtn.disabled    = true;
  schedulerSaveBtn.textContent = 'Saving…';

  try {
    const res = await fetch('/scheduler/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled, days, time }),
    });

    if (!res.ok) {
      const err = await res.json();
      showQueueStatus(err.detail || 'Failed to save schedule.', 'error');
      return;
    }

    const data = await res.json();
    showQueueStatus('Schedule saved.');

    if (data.next_run) {
      const d = new Date(data.next_run);
      nextRunHint.textContent = `Next run: ${d.toLocaleString()}`;
    } else {
      nextRunHint.textContent = enabled ? '' : 'Scheduler disabled';
    }

    // Refresh the status bar so the 🟢/🔴 indicator updates
    loadQueueStatus();

  } catch {
    showQueueStatus('Network error.', 'error');
  } finally {
    schedulerSaveBtn.disabled    = false;
    schedulerSaveBtn.textContent = 'Save Schedule';
  }
});
```

---

## 5. `ui/styles.css` — append scheduler styles

Append the following to the bottom of `styles.css`:

```css
/* ============================================================
   Scheduler settings panel
   ============================================================ */
.scheduler-settings {
  margin-top: 32px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.scheduler-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}

.scheduler-title {
  font-family: var(--font-ui);
  font-size: 0.85rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

/* ── Toggle switch ── */
.toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.toggle-label input[type="checkbox"] {
  display: none;
}

.toggle-track {
  position: relative;
  width: 36px;
  height: 20px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 10px;
  transition: background 0.2s, border-color 0.2s;
}

.toggle-label input:checked + .toggle-track {
  background: var(--accent-red);
  border-color: var(--accent-red);
}

.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  background: var(--text-secondary);
  border-radius: 50%;
  transition: transform 0.2s, background 0.2s;
}

.toggle-label input:checked + .toggle-track .toggle-thumb {
  transform: translateX(16px);
  background: #fff;
}

.toggle-text {
  font-family: var(--font-ui);
  font-size: 0.8rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-secondary);
  min-width: 56px;
}

/* ── Scheduler body ── */
.scheduler-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  transition: opacity 0.2s;
}

.scheduler-body--disabled {
  opacity: 0.35;
  pointer-events: none;
}

/* ── Day picker ── */
.day-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.day-picker-label {
  font-size: 0.78rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.day-pills {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.day-pill {
  cursor: pointer;
}

.day-pill input[type="checkbox"] {
  display: none;
}

.day-pill span {
  display: inline-block;
  padding: 5px 11px;
  border-radius: var(--radius);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  font-family: var(--font-ui);
  font-size: 0.8rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
  user-select: none;
}

.day-pill input:checked + span {
  background: var(--accent-red);
  border-color: var(--accent-red);
  color: #fff;
}

/* ── Time picker ── */
.time-picker-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.time-input {
  background: var(--input-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: 0.9rem;
  padding: 7px 10px;
  width: 120px;
}

.time-input:focus {
  border-color: var(--accent-red);
  outline: none;
}

.time-hint {
  font-size: 0.78rem;
  color: var(--text-muted);
  font-style: italic;
}

/* ── Save row ── */
.scheduler-save-row {
  display: flex;
}
```

---

## Summary of changes

| File | Change |
|---|---|
| `server/scheduler.py` | Add `import json` + `from pathlib import Path`; replace `start_scheduler()` with 5 new functions |
| `server/api.py` | Extend scheduler import; add `SchedulerConfigRequest` + `SchedulerConfigResponse` schemas; add `GET /scheduler/config` + `POST /scheduler/config` endpoints |
| `ui/index.html` | Insert scheduler settings panel between queue status message and queue list sections |
| `ui/app.js` | Update tab-switch handler to call `loadSchedulerConfig()`; append scheduler settings JS block |
| `ui/styles.css` | Append scheduler panel, toggle, day pill, time picker styles |
| `data/scheduler_config.json` | Auto-created on first save — do not create manually |

---

## Notes for Claude Code

- The five new functions in `scheduler.py` replace the single existing `start_scheduler()`
  function only — everything else in that file (`stop_scheduler`, `process_next_queued_fighter`,
  `_has_been_posted`, `_run_pipeline`) is untouched
- `apply_scheduler_config()` uses `scheduler.add_job(..., replace_existing=True)` — this
  reschedules the live job without a restart. If disabled or no days selected, it calls
  `scheduler.remove_job("queue_job")` wrapped in a bare `except` because the job may not
  exist if it was never scheduled
- Valid day abbreviations map directly to APScheduler's `day_of_week` cron field:
  `sun mon tue wed thu fri sat`
- `GET /scheduler/config` returns `next_run` as an ISO 8601 string from
  `job.next_run_time.isoformat()`. The UI renders it with `new Date(data.next_run).toLocaleString()`
- The day pill toggle is pure CSS — the hidden checkbox drives the `:checked + span` selector.
  The JS only reads `.day-pill input:checked` values at save time
- The tab-switch handler already exists in `app.js` — only add `loadSchedulerConfig()` to
  the `if (btn.dataset.tab === 'queue')` branch, do not duplicate the handler
- `data/scheduler_config.json` is written by `save_scheduler_config()` on the first POST
  to `/scheduler/config`. Until then, `load_scheduler_config()` returns the hardcoded
  defaults (Mon–Fri, 09:00, enabled)
