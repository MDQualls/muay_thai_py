# Muay Thai Fighter Card App

A web app that generates stylized Muay Thai fighter profile cards and posts them to Instagram. Enter a fighter's name, and the app fetches their Wikipedia record, enriches it with Claude AI, renders a three-slide carousel JPEG, and publishes it to Instagram — all from a browser at `localhost:8000`.

Cards can be generated on demand via the Generate tab, or queued up and posted automatically on a configurable schedule. The scheduler runs inside Docker and does not require the browser to be open.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- A `.env` file with your credentials (see Setup below)

---

## Setup

1. **Copy the example env file and fill in your keys:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your Anthropic API key, Meta/Instagram credentials, and Cloudflare R2 credentials.

2. **Build and start the app:**
   ```bash
   docker compose up --build
   ```

3. **Open the app:**
   ```
   http://localhost:8000
   ```

4. **Run in the background (no terminal required):**
   ```bash
   docker compose up -d
   ```

---

## How it works

The app has three tabs:

**Generate** — Enter a fighter name and run the full pipeline manually. Preview the three-slide carousel, edit the caption, and post to Instagram with one click.

**Queue** — Add fighters individually or in bulk, import from the seed list, and manage the queue. Each fighter moves through `pending → processing → done` (or `failed`). Failed items can be edited and retried inline. A filter toggle hides completed fighters so you can focus on what's left.

**Scheduler** — Configure which days the scheduler runs, what time, and whether it is enabled. Settings are saved immediately and applied to the running app without a restart. The next scheduled run time is shown after saving.

---

## Pipeline

Each fighter card goes through five stages:

```
Wikipedia API → Claude AI enrichment → Playwright render → Cloudflare R2 upload → Instagram post
```

The scheduler picks the next pending fighter from the queue, runs the full pipeline headlessly, and marks the item done or failed. Already-posted fighters are skipped automatically even if they are re-added to the queue.

---

## Server Modules

| Module | Responsibility |
|---|---|
| `server/api.py` | FastAPI routes, request validation, HTTP responses |
| `server/config.py` | App settings loaded from `.env` via pydantic-settings |
| `server/exceptions.py` | Custom exception classes for each pipeline stage |
| `server/models.py` | SQLModel table definitions (Fighter, FighterProfile, Card, InstagramPost, FighterQueue) |
| `server/database.py` | SQLite engine, session factory, table initialization |
| `server/scheduler.py` | APScheduler setup, queue processing, headless pipeline runner, config load/save |
| `server/fetcher.py` | Fetches fighter data from the Wikipedia API |
| `server/enricher.py` | Sends raw data to Claude API and parses enriched profile |
| `server/caption_builder.py` | Builds the Instagram caption from enriched fighter data |
| `server/renderer.py` | Renders Jinja2 card templates to JPEG via Playwright |
| `server/uploader.py` | Uploads card JPEGs to Cloudflare R2, returns public URLs |
| `server/publisher.py` | Posts carousel to Instagram via Meta Graph API |

---

## Data files

| File | Purpose |
|---|---|
| `data/muaythai.db` | SQLite database — persists via Docker volume |
| `data/fighters.json` | Seed list of fighter names for bulk queue import |
| `data/scheduler_config.json` | Saved scheduler settings (auto-created on first save) |

---

## Useful commands

```bash
# View live logs
docker compose logs app -f

# View last 50 log lines
docker compose logs app --tail=50

# Stop the app
docker compose down
```

---

## Notes

- `main.py` is for running the app **outside Docker** during local development. Inside Docker, uvicorn is called directly from the `CMD` in the Dockerfile.
- Generated card JPEGs are saved to `output/` and persist via a Docker volume.
- The scheduler runs inside the Docker container and continues posting on schedule even when the browser is closed. It only stops if the container stops.
- Scheduler configuration is stored in `data/scheduler_config.json`. If that file does not exist, the scheduler defaults to Mon–Fri at 09:00.
- Fighter data comes from Wikipedia only. Cards for fighters with thin Wikipedia articles may produce incomplete enrichment.
