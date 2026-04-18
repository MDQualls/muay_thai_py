# Muay Thai Cards — Post-MVP Feature Backlog

This document tracks features and improvements planned after the MVP pipeline was completed.
The MVP covers: fetcher → enricher → renderer → uploader → publisher → Instagram carousel post,
with a working UI at localhost:8000 and a SQLite database persisting all runs.

---

## ✅ Completed Post-MVP Items

- **Publisher status polling** — replaced hardcoded `asyncio.sleep()` delays with proper
  Graph API container status polling. The publisher now checks the container's `status_code`
  field and waits until it returns `FINISHED` before proceeding to the next step.

---

## Remaining Items

---

### 1. Meta Access Token Refresh

**What:** The Meta long-lived access token expires approximately 60 days after generation.
When it expires, `/post` will silently fail with an auth error from the Graph API.

**Why it matters:** Without a reminder or refresh mechanism, the app will stop posting
with no obvious error message to the user.

**Options:**

**Option A — Log expiry warning on startup (simplest)**
Store the token generation date in `.env` or a config file. On app startup, calculate
days remaining and log a warning if under 14 days:

```python
TOKEN_GENERATED_DATE = "2026-04-12"  # update when you refresh

days_remaining = (expiry_date - datetime.now()).days
if days_remaining < 14:
    logger.warning("Meta access token expires in %d days — refresh soon", days_remaining)
```

**Option B — Automatic refresh via Graph API**
The Graph API has an endpoint to exchange a still-valid long-lived token for a fresh one.
Can be called programmatically before each post or on a schedule.

```
GET https://graph.facebook.com/v25.0/oauth/access_token
    ?grant_type=fb_exchange_token
    &client_id={app_id}
    &client_secret={app_secret}
    &fb_exchange_token={current_token}
```

Store the new token back to `.env` and reload settings.

**References:**
- [Meta — Long-lived token refresh](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived)

---

### 2. Code Cleanup and Refactoring Session

**What:** A dedicated session to clean up the codebase now that the full pipeline is
understood. Written during rapid iterative development — now that it works, make it clean.

**Areas to address:**

- **Base class for wiki services** — `WikiSearcher` and `WikiContentGetter` share
  `self.logger`, `_handle_fetch_exception()`, and the `httpx.AsyncClient` pattern.
  A `BaseWikiService` class would eliminate the duplication. Defer until TheSportsDB
  or another data source is added, at which point the pattern becomes worth abstracting.

- **Remove `sportsdb_id` from `Fighter` model** — added during the TheSportsDB phase
  which was dropped. Dead field in the schema.

- **Ruff lint pass** — run `ruff check` across the whole codebase and fix all warnings.
  Several typos in docstrings, inconsistent spacing, and unused imports likely remain.

- **Test coverage** — the test files are all integration tests that hit real APIs. Add
  unit tests for pure functions like `caption_builder.build_caption()`,
  `PathHandler.make_output_path()`, and the prompt builder.

- **Remove stale TODO comments** — several TODO comments in `api.py` and other files
  were completed but the comments weren't removed.

---

### 3. Fighter Images on Cards

**What:** Pull a fighter photo from Wikipedia, remove the background using `rembg`,
and incorporate the fighter image into the card design — particularly slide 1 (impact slide).

**Why it matters:** Cards with fighter photos will stop the scroll far more effectively
than text-only cards. This is a significant visual upgrade.

**Implementation approach:**

**Step 1 — Fetch image from Wikipedia**
The Wikipedia API returns a thumbnail URL in the page summary endpoint:
```
GET https://en.wikipedia.org/api/rest_v1/page/summary/{title}
```
Response includes `thumbnail.source` — a direct image URL. Add this to the fetcher
return dict as `wikipedia_thumbnail`.

**Step 2 — Download the image**
In `fetcher.py`, download the thumbnail bytes using `httpx` and save to a temp path
in `output/`.

**Step 3 — Remove background with `rembg`**
`rembg` is already in the dependencies. Run it in a thread pool:
```python
from rembg import remove
result = await asyncio.to_thread(remove, image_bytes)
```
Returns RGBA PNG bytes with the background removed.

**Step 4 — Save the cutout**
Save the cutout as a PNG (must keep PNG for transparency) alongside the output JPEGs.

**Step 5 — Pass image path to the Jinja2 template**
Add `fighter_image_path` to the `render_slide()` call and reference it in
`slide_1_impact.html` using an absolute file path so Playwright can find it.
Note: Playwright needs a `file://` URI or a data URI for local images — use base64:

```python
import base64
with open(cutout_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()
# Pass as: "data:image/png;base64,{img_b64}"
```

**Step 6 — Update `slide_1_impact.html` template**
Add an image element to the impact slide, positioned to overlap with the content.
The cutout with transparent background composites naturally over the dark card.

**References:**
- [rembg GitHub](https://github.com/danielgatis/rembg)
- [Wikipedia REST API — page summary](https://en.wikipedia.org/api/rest_v1/)
- [Playwright — loading local images](https://playwright.dev/python/docs/api/class-page#page-set-content)

---

### 4. Fight Record Parsing from Wikipedia

**What:** Wikipedia fight records are stored in structured HTML tables that the plain
text extract doesn't capture. Parse these tables to get accurate W/L/KO/draw numbers
instead of returning `null` from the enricher.

**Why it matters:** The record is a key piece of fighter data that's currently missing
from all cards. "270-42" is more compelling than nothing.

**Implementation approach:**

The Wikipedia API supports returning page content as HTML (not just plain text):
```
GET https://en.wikipedia.org/w/api.php
    ?action=parse
    &pageid={pageid}
    &prop=text
    &format=json
```

Returns the full rendered HTML of the page. Use `BeautifulSoup4` to parse the fight
record table — re-add it to `pyproject.toml` since it was removed earlier.

The fight record table on Wikipedia Muay Thai pages follows a consistent structure:
- Class names like `wikitable` identify it
- Columns: Result, Record, Opponent, Method, Event, Date, Notes

Parse the table and extract:
- Total wins (count of "Win" rows)
- Total losses (count of "Loss" rows)  
- KO/TKO wins (count of "Win" rows where Method contains "KO" or "TKO")
- Draw count

Add a new method `_fetch_fight_record(pageid)` to `WikiContentGetter` or a new
`WikiRecordParser` class in `server/service/wiki/`.

**Note:** This requires adding `beautifulsoup4` back to `pyproject.toml` and rebuilding
the Docker image.

**References:**
- [BeautifulSoup4 documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Wikipedia API — parse action](https://www.mediawiki.org/wiki/API:Parse)

---

### 5. Post Scheduling

**What:** Automatically generate and post a fighter card on a schedule — e.g. every
Tuesday and Friday at 9am — without having to manually open the app and click Generate.

**Why it matters:** Consistent posting is the primary driver of Instagram account growth.
Manual posting relies on remembering and having time. A scheduler removes both obstacles.

**Implementation approach:**

`APScheduler` is the standard Python scheduling library. Add it to `pyproject.toml`
and wire it into the FastAPI lifespan:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    scheduler.add_job(scheduled_post, "cron", day_of_week="tue,fri", hour=9)
    scheduler.start()
    yield
    scheduler.shutdown()
```

The `scheduled_post` function would need a pre-defined list of fighters to cycle through,
or a mechanism to pick a fighter automatically (random from a list, current champion,
fighter of the week, etc.).

**Fighter selection options:**
- A hardcoded rotation list in `config.py` or a JSON file
- Random selection from a curated list stored in the database
- A new `ScheduledFighter` table with a queue of upcoming fighters

**References:**
- [APScheduler documentation](https://apscheduler.readthedocs.io/en/stable/)
- [APScheduler with FastAPI](https://apscheduler.readthedocs.io/en/stable/userguide.html)

---

### 6. Card Design Polish

**What:** Iterate on the three slide templates now that the full pipeline is working
and you can see real cards with real fighter data.

**Known issues to address:**
- Slide 1 bottom half still has some dead space depending on content length
- Long fighter names can push against the card edge at 120px
- The decorative background number on slide 1 could be more impactful
- Slide 2 right column is sparse when record data is null
- Font sizes on slides 2 and 3 could go larger now that content is split across slides

**Approach:** Run `test/test_renderer.py` with hardcoded data for iteration speed —
no need to hit Wikipedia and Claude on every design tweak. Open the output PNGs
from the volume-mounted `output/` directory directly in macOS Preview to see changes.

---

## Priority Order

| Priority | Item | Effort | Impact |
|---|---|---|---|
| High | Meta token refresh | Low | Prevents silent failure |
| High | Fight record parsing | Medium | Improves card quality |
| High | Fighter images | High | Major visual upgrade |
| Medium | Code cleanup | Medium | Code quality |
| Medium | Post scheduling | Medium | Account growth |
| Low | Card design polish | Ongoing | Visual quality |
