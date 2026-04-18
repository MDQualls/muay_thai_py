/**
 * app.js — Muay Thai Cards frontend logic
 *
 * Wires up the fighter card generation pipeline UI:
 *   1. User enters a fighter name and clicks Generate
 *   2. POST /generate → pipeline runs on the server
 *   3. On success: show card preview (GET /preview), caption, and Post button
 *   4. User edits caption and clicks Post to Instagram
 *   5. POST /post → returns Instagram post ID
 */

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------

const fighterInput   = document.getElementById('fighter-input');
const generateBtn    = document.getElementById('generate-btn');
const progressSection = document.getElementById('progress-section');
const stepScrape     = document.getElementById('step-scrape');
const stepEnrich     = document.getElementById('step-enrich');
const stepRender     = document.getElementById('step-render');
const previewSection  = document.getElementById('preview-section');
const carouselTrack   = document.getElementById('carousel-track');
const carouselDots    = document.querySelectorAll('.dot');
const captionInput    = document.getElementById('caption-input');
const postBtn        = document.getElementById('post-btn');
const statusSection  = document.getElementById('status-section');
const statusMessage  = document.getElementById('status-message');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function showStatus(message, type = 'success') {
  statusMessage.textContent = message;
  statusMessage.className = `status-message ${type}`;
  statusSection.classList.remove('hidden');
}

function hideStatus() {
  statusSection.classList.add('hidden');
}

function setStep(stepEl, state) {
  // state: 'pending' | 'active' | 'done' | 'error'
  const icons = { pending: '⬜', active: '🔄', done: '✅', error: '❌' };
  stepEl.querySelector('.step-icon').textContent = icons[state] ?? '⬜';
  stepEl.className = `step ${state}`;
}

function resetSteps() {
  [stepScrape, stepEnrich, stepRender].forEach(s => setStep(s, 'pending'));
}

function goToSlide(index) {
  carouselTrack.style.transform = `translateX(-${index * 100}%)`;
  carouselDots.forEach((dot, i) => dot.classList.toggle('active', i === index));
}

carouselDots.forEach(dot => {
  dot.addEventListener('click', () => goToSlide(Number(dot.dataset.index)));
});

// ---------------------------------------------------------------------------
// Generate flow
// ---------------------------------------------------------------------------

// TODO: on Generate button click
//   1. Validate that the input is not empty
//   2. Show the progress section, reset all steps
//   3. Disable the Generate button while in progress
//   4. Mark stepScrape as active
//   5. POST /generate with body { fighter_name: inputValue }
//   6. As the response arrives (or at key milestones), advance step indicators:
//        stepScrape → done, stepEnrich → active → done, stepRender → active → done
//      (The backend is a single await, so advance all on success for now)
//   7. On success:
//        - Populate captionInput with response.caption
//        - Set cardPreview.src to "/preview?" + Date.now() (cache bust)
//        - Show previewSection
//        - Hide progress section
//   8. On error:
//        - Mark the current step as error
//        - Show error status message with detail from the response
//   9. Re-enable the Generate button

generateBtn.addEventListener('click', async () => {
  const fighterName = fighterInput.value.trim();

  if (!fighterName) {
    showStatus('Enter a fighter name first.', 'error');
    return;
  }

  hideStatus();
  progressSection.classList.remove('hidden');
  previewSection.classList.add('hidden');
  resetSteps();
  generateBtn.disabled = true;

  setStep(stepScrape, 'active');
  let currentStep = stepScrape;

  const enrichTimer = setTimeout(() => {
    setStep(stepScrape, 'done');
    setStep(stepEnrich, 'active');
    currentStep = stepEnrich;
  }, 3000);

  const renderTimer = setTimeout(() => {
    setStep(stepEnrich, 'done');
    setStep(stepRender, 'active');
    currentStep = stepRender;
  }, 8000);

  try {
    const response = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fighter_name: fighterName }),
    });

    clearTimeout(enrichTimer);
    clearTimeout(renderTimer);

    if (!response.ok) {
      const err = await response.json();
      setStep(currentStep, 'error');
      showStatus(err.detail || 'Generation failed.', 'error');
      return;
    }

    const data = await response.json();

    setStep(stepScrape, 'done');
    setStep(stepEnrich, 'done');
    setStep(stepRender, 'done');

    const t = Date.now();
    document.getElementById('slide-1').src = `/preview?slide=1&t=${t}`;
    document.getElementById('slide-2').src = `/preview?slide=2&t=${t}`;
    document.getElementById('slide-3').src = `/preview?slide=3&t=${t}`;
    goToSlide(0);
    captionInput.value = data.caption;

    setTimeout(() => {
      progressSection.classList.add('hidden');
      previewSection.classList.remove('hidden');
    }, 800);

  } catch (err) {
    clearTimeout(enrichTimer);
    clearTimeout(renderTimer);
    setStep(currentStep, 'error');
    showStatus('Network error. Is the server running?', 'error');
  } finally {
    generateBtn.disabled = false;
  }
});

fighterInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') generateBtn.click();
});

// ---------------------------------------------------------------------------
// Post flow
// ---------------------------------------------------------------------------

// TODO: on Post button click
//   1. Disable the Post button while in progress
//   2. Read caption from captionInput.value
//   3. POST /post with body { caption: captionText }
//   4. On success:
//        - Show success status message including the instagram_post_id
//        - Keep the preview visible
//   5. On error:
//        - Show error status message with detail from the response
//   6. Re-enable the Post button

postBtn.addEventListener('click', async () => {
  const caption = captionInput.value.trim();

  postBtn.disabled = true;
  postBtn.textContent = 'Posting...';
  postBtn.classList.add('btn-loading');
  hideStatus();

  try {
    const response = await fetch('/post', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caption: caption || null }),
    });

    if (!response.ok) {
      const err = await response.json();
      showStatus(err.detail || 'Post failed.', 'error');
      return;
    }

    const data = await response.json();
    showStatus(`Posted to Instagram — ID: ${data.instagram_post_id}`, 'success');

  } catch (err) {
    showStatus('Network error. Is the server running?', 'error');
  } finally {
    postBtn.disabled = false;
    postBtn.textContent = 'Post to Instagram';
    postBtn.classList.remove('btn-loading');
  }
});

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
    if (btn.dataset.tab === 'scheduler') {
      loadSchedulerConfig();
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
    applyQueueFilter(filterDoneToggle.checked);

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
      body: JSON.stringify({ enabled, days, time, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }),
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
