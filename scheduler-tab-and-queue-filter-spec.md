# Scheduler Tab & Queue Filter — Implementation Spec

## Context

The scheduler settings panel currently lives inside the Queue tab, embedded below
the queue status message. This spec moves it to its own dedicated tab and adds a
filter toggle to the Queue tab that hides processed (done) fighters from the list.

No backend changes are required. This is purely a UI reorganisation plus one small
JS addition for the filter. All existing API endpoints, schemas, and Python files
remain untouched.

---

## Part 1 — Move Scheduler to its own tab

### What changes

- `ui/index.html` — add a third tab button (`Scheduler`), add a new `tab-panel`
  for it containing the scheduler settings markup, remove the scheduler settings
  section from the Queue tab
- `ui/app.js` — update the tab-switch handler to call `loadSchedulerConfig()` when
  the Scheduler tab is opened (instead of when the Queue tab is opened), remove the
  `loadSchedulerConfig()` call from the Queue tab branch
- `ui/styles.css` — no structural changes needed; the scheduler panel styles already
  apply by class name regardless of which tab they live in. If the scheduler panel
  styles have not yet been appended, append them now (see Part 1, section 3 below)

---

### 1. `ui/index.html` — full replacement of `<nav>` and tab panels

Replace the existing `<nav class="tab-nav">` block and everything inside
`<main class="app-main">` with the following. The Generate tab content is
identical to what exists — do not change it. The Queue tab loses the scheduler
settings section. The Scheduler tab is new.

```html
    <main class="app-main">

      <!-- Tab navigation -->
      <nav class="tab-nav">
        <button class="tab-btn active" data-tab="generate">Generate</button>
        <button class="tab-btn" data-tab="queue">Queue</button>
        <button class="tab-btn" data-tab="scheduler">Scheduler</button>
      </nav>

      <!-- ── Generate Tab ── -->
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

        <!-- Queue list header with filter toggle -->
        <section class="queue-list-section">
          <div class="queue-list-header">
            <span class="queue-list-title">Queue</span>
            <label class="toggle-label" id="filter-toggle-label" title="Hide processed fighters">
              <input type="checkbox" id="filter-done-toggle" />
              <span class="toggle-track">
                <span class="toggle-thumb"></span>
              </span>
              <span class="toggle-text" id="filter-toggle-text">Show All</span>
            </label>
          </div>
          <div id="queue-list" class="queue-list">
            <p class="queue-empty">Queue is empty. Add fighters above.</p>
          </div>
        </section>

      </div>

      <!-- ── Scheduler Tab ── -->
      <div class="tab-panel hidden" id="tab-scheduler">

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

      </div>

    </main>
```

---

### 2. `ui/app.js` — update the tab-switch handler

Locate the existing tab-switch handler. It currently reads:

```javascript
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.remove('hidden');
    if (btn.dataset.tab === 'queue') {
      loadQueue();
      loadQueueStatus();
      loadSchedulerConfig();
    }
  });
});
```

Replace it with:

```javascript
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
    if (btn.dataset.tab === 'scheduler') {
      loadSchedulerConfig();
    }
  });
});
```

---

### 3. `ui/styles.css` — scheduler panel styles

If the following styles are not already present at the bottom of `styles.css`, append
them now. If they are already present, skip this step.

```css
/* ============================================================
   Scheduler settings panel
   ============================================================ */
.scheduler-settings {
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

/* ── Toggle switch (shared by scheduler enable and filter toggle) ── */
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

---

## Part 2 — Queue filter toggle

### What it does

A toggle sits in the queue list header. By default it is **off** — all fighters are
visible. When toggled **on**, fighters with `status === "done"` are hidden from view.
Toggling it back off restores them. This is purely client-side — no API calls, no
re-fetch. The full list is always loaded; the toggle just shows/hides rows with CSS.

The label reads **"Show All"** when off (everything visible) and **"Hide Done"** when
on (done items hidden). This makes the state self-describing regardless of which way
the user reads it.

---

### 1. `ui/index.html` — already handled in Part 1

The filter toggle markup is included in the Queue tab HTML above:

```html
          <div class="queue-list-header">
            <span class="queue-list-title">Queue</span>
            <label class="toggle-label" id="filter-toggle-label" title="Hide processed fighters">
              <input type="checkbox" id="filter-done-toggle" />
              <span class="toggle-track">
                <span class="toggle-thumb"></span>
              </span>
              <span class="toggle-text" id="filter-toggle-text">Show All</span>
            </label>
          </div>
```

No additional HTML changes needed.

---

### 2. `ui/app.js` — add filter toggle logic

Append the following block to the bottom of `app.js`:

```javascript
// --- Queue filter toggle ---

const filterDoneToggle  = document.getElementById('filter-done-toggle');
const filterToggleText  = document.getElementById('filter-toggle-text');

filterDoneToggle.addEventListener('change', () => {
  const hideDone = filterDoneToggle.checked;
  filterToggleText.textContent = hideDone ? 'Hide Done' : 'Show All';
  applyQueueFilter(hideDone);
});

function applyQueueFilter(hideDone) {
  document.querySelectorAll('#queue-list .queue-item').forEach(item => {
    const isDone = item.dataset.status === 'done';
    // When hideDone is true, hide items whose status is done.
    // All other statuses (pending, processing, failed) are always visible.
    item.classList.toggle('queue-item--hidden', hideDone && isDone);
  });
}
```

Also update `loadQueue()` so that the filter is re-applied after the list re-renders.
The existing `loadQueue()` function ends with `attachQueueListeners()`. Add one line
after it:

```javascript
// Inside loadQueue(), after: queueList.innerHTML = items.map(renderQueueItem).join('');
//                             attachQueueListeners();
// Add:
applyQueueFilter(filterDoneToggle.checked);
```

The full updated `loadQueue()` function should read:

```javascript
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
    applyQueueFilter(filterDoneToggle.checked);

  } catch {
    showQueueStatus('Failed to load queue.', 'error');
  }
}
```

---

### 3. `ui/styles.css` — add queue list header and filter styles

Append to the bottom of `styles.css`:

```css
/* ============================================================
   Queue list header (title + filter toggle)
   ============================================================ */
.queue-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.queue-list-title {
  font-family: var(--font-ui);
  font-size: 0.8rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

/* ============================================================
   Queue item hidden by filter
   ============================================================ */
.queue-item--hidden {
  display: none !important;
}
```

---

## Summary of changes

| File | Change |
|---|---|
| `ui/index.html` | Add Scheduler tab button; move scheduler settings markup to new `tab-scheduler` panel; add filter toggle to queue list header in Queue tab |
| `ui/app.js` | Update tab-switch handler to load scheduler config on Scheduler tab open, not Queue tab; append filter toggle logic; update `loadQueue()` to call `applyQueueFilter()` after render |
| `ui/styles.css` | Append scheduler panel styles if not already present; append queue list header and `queue-item--hidden` styles |

**No backend changes.** No Python files, no API endpoints, no schemas are modified.

---

## Notes for Claude Code

- The toggle component (`.toggle-label` / `.toggle-track` / `.toggle-thumb`) is reused
  for both the scheduler enabled toggle and the queue filter toggle — the same CSS class
  names drive both. No duplication needed.
- `applyQueueFilter()` reads `item.dataset.status` which is set on each `.queue-item`
  via `data-status="${item.status}"` in `renderQueueItem()`. This attribute already
  exists in the rendered markup — no changes to `renderQueueItem()` are needed.
- The filter state is not persisted — it resets to "Show All" on each page load and
  each time the Queue tab is opened. This is intentional; it is a session-level view
  preference.
- The filter toggle label intentionally reads "Show All" when off and "Hide Done" when
  on. Do not change this to "Filter" or "Toggle" — the labels describe the current
  visible state, not the action.
- Do not remove the `scheduler-settings` section from `index.html` before confirming
  the new `tab-scheduler` panel is in place. Move, don't delete.
- If the scheduler panel CSS already exists in `styles.css` from the previous
  implementation, skip section 1.3 entirely — do not duplicate those rules.
- The `queue-list-section` div loses its `margin-top: 32px` role as top-level spacer
  now that it has an internal header. If spacing looks off, adjust `margin-top` on
  `.queue-list-section` in the existing CSS rather than adding new rules.
