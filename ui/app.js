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
const previewSection = document.getElementById('preview-section');
const cardPreview    = document.getElementById('card-preview');
const captionInput   = document.getElementById('caption-input');
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

    cardPreview.src = `/preview?t=${Date.now()}`;
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
