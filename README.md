# Muay Thai Fighter Card App

A local web app that generates stylized Muay Thai fighter profile cards and posts them to Instagram. Enter a fighter's name, and the app scrapes their record, enriches it with Claude AI, renders a 1080×1080 PNG card, and publishes it to Instagram — all from a browser at `localhost:8000`.

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

---

## Server Modules

| Module | Responsibility |
|---|---|
| `server/api.py` | FastAPI routes, request validation, HTTP responses |
| `server/config.py` | App settings loaded from `.env` via pydantic-settings |
| `server/exceptions.py` | Custom exception classes for each pipeline stage |
| `server/models.py` | SQLModel table definitions (Fighter, FighterProfile, Card, InstagramPost) |
| `server/database.py` | SQLite engine, session factory, table initialization |
| `server/scraper.py` | Scrapes fighter data from Tapology and ONE Championship |
| `server/enricher.py` | Sends raw data to Claude API and parses enriched profile |
| `server/renderer.py` | Renders Jinja2 card template to PNG via Playwright |
| `server/uploader.py` | Uploads card PNG to Cloudflare R2, returns public URL |
| `server/publisher.py` | Posts image to Instagram via Meta Graph API |

---

## Notes

- `main.py` is for running the app **outside Docker** during local development. Inside Docker, uvicorn is called directly from the `CMD` in the Dockerfile.
- Generated card PNGs are saved to `output/` and persist via a Docker volume.
- The SQLite database is stored in `data/muaythai.db` and persists via a Docker volume.
