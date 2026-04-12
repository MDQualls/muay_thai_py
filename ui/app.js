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

  // TODO: implement generate flow (see steps above)
  console.log('Generate clicked for:', fighterName);
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

  // TODO: implement post flow (see steps above)
  console.log('Post clicked with caption:', caption);
});
