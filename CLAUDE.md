# CLAUDE.md — Muay Thai Fighter Card App

This file tells Claude Code how to think, write, and behave when working on this codebase.
Read it before touching any file.

---

## What This App Is

A local web app that scrapes Muay Thai fighter data, enriches it with Claude AI, renders a
styled fighter profile card as a PNG, and posts it to Instagram. It runs in Docker, served
at localhost:8000 via FastAPI, with a vanilla JS frontend.

---

## Python Philosophy

Write Python that a senior engineer would be proud of. That means:

- **Explicit over implicit** — if something isn't obvious, name it clearly or add a comment
- **Flat over nested** — guard clauses and early returns over deeply nested if/else
- **Small functions** — each function does one thing. If you can't describe it in one sentence, split it
- **No clever one-liners** — readable beats compact every time
- **No magic numbers** — name your constants

---

## Type Hints — Always, Everywhere

Every function signature gets full type hints. No exceptions.

```python
# WRONG
def get_fighter_data(name):
    ...

# RIGHT
def get_fighter_data(fighter_name: str) -> dict[str, Any]:
    ...
```

Use types from the `typing` module for complex types. Use `|` union syntax (Python 3.10+):

```python
def find_fighter(name: str) -> dict[str, Any] | None:
    ...
```

Use dataclasses or TypedDicts for structured data that moves between modules — not bare dicts
with unknown shapes.

```python
from dataclasses import dataclass

@dataclass
class FighterProfile:
    name: str
    nickname: str | None
    record: str
    gym: str
    nationality: str
    fight_history: list[dict[str, Any]]
```

---

## Error Handling

This app talks to external services — scrapers, Claude API, Meta Graph API, R2. Things will fail.
Handle it explicitly. Never let exceptions bubble up silently.

```python
# WRONG
def upload_card(card_path: str) -> str:
    result = s3.upload_file(card_path, bucket, key)
    return build_url(key)

# RIGHT
def upload_card(card_path: str) -> str:
    try:
        s3.upload_file(card_path, bucket, key)
    except ClientError as e:
        logger.error("R2 upload failed: %s", e)
        raise UploadError(f"Failed to upload {card_path}") from e
    return build_url(key)
```

Define custom exceptions in `server/exceptions.py`:

```python
class ScraperError(Exception): ...
class EnrichmentError(Exception): ...
class RenderError(Exception): ...
class UploadError(Exception): ...
class PublishError(Exception): ...
```

FastAPI routes catch these and return appropriate HTTP responses — they do not let
raw exceptions reach the client.

---

## Logging

Use the standard `logging` module. No `print()` statements in production code.

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Scraping fighter: %s", fighter_name)
logger.warning("No record found for %s, using defaults", fighter_name)
logger.error("Claude API call failed: %s", e)
```

Configure logging once at app startup in `api.py`. Each module gets its own logger via
`__name__` — never pass loggers around as arguments.

---

## Async — Use It Properly

FastAPI is async. Write async route handlers. Use `httpx.AsyncClient` for all HTTP calls,
not `requests`.

```python
# WRONG — blocks the event loop
import requests
response = requests.get(url)

# RIGHT
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get(url)
```

For Playwright, use the async API:

```python
from playwright.async_api import async_playwright

async def render_card(data: FighterProfile) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ...
```

CPU-bound work (like `rembg` background removal) should be run in a thread pool via
`asyncio.to_thread()` to avoid blocking:

```python
result = await asyncio.to_thread(remove_background, image_bytes)
```

---

## Module Responsibilities — Keep Them Clean

Each module in `server/` owns exactly one layer of the pipeline. Do not bleed
responsibilities across modules.

| Module | Owns | Does NOT own |
|---|---|---|
| `fetcher.py` | Wikipedia API + TheSportsDB API calls, raw data extraction | Any AI calls, any rendering |
| `enricher.py` | Claude API calls, prompt building, response parsing | Any scraping, any file I/O |
| `renderer.py` | Jinja2 templating, Playwright, PNG output | Any API calls, any data fetching |
| `uploader.py` | R2/S3 client, file upload, URL construction | Any rendering, any posting |
| `publisher.py` | Meta Graph API calls, Instagram post creation | Any file I/O, any image work |
| `api.py` | FastAPI routes, request validation, HTTP responses | Any business logic |
| `models.py` | SQLModel table definitions, relationships | Any queries, any business logic |
| `database.py` | Engine creation, session factory, table init | Any model definitions, any routes |

If you find yourself importing `scraper` from `renderer` or `enricher` from `publisher`,
stop and reconsider the design.

---

## Database — SQLModel Patterns

The database layer uses **SQLModel**, which unifies SQLAlchemy models and Pydantic schemas
into a single class definition. It feels native to FastAPI because it was designed for it.

### Sessions via Dependency Injection

Never create sessions directly inside business logic. Always inject them via FastAPI's
`Depends()` system:

```python
# database.py — define once
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

# api.py — inject everywhere needed
@app.get("/fighters")
async def list_fighters(session: Session = Depends(get_session)) -> list[Fighter]:
    return session.exec(select(Fighter)).all()
```

### Querying

Use SQLModel's `select()` — not raw SQL strings, not the SQLAlchemy ORM `.query()` style.

```python
from sqlmodel import select

# Single record by ID
fighter = session.get(Fighter, fighter_id)

# Query with filter
statement = select(Fighter).where(Fighter.name == name)
fighter = session.exec(statement).first()

# All records
fighters = session.exec(select(Fighter)).all()

# With relationship
statement = select(Card).where(Card.fighter_id == fighter_id)
cards = session.exec(statement).all()
```

### Writing Records

Always commit explicitly. Never assume auto-commit.

```python
def save_fighter(session: Session, data: dict[str, Any]) -> Fighter:
    fighter = Fighter(**data)
    session.add(fighter)
    session.commit()
    session.refresh(fighter)  # refresh to get the auto-generated id
    return fighter
```

### Upsert Pattern

This app will frequently re-process fighters. Check before inserting:

```python
def upsert_fighter(session: Session, name: str, data: dict[str, Any]) -> Fighter:
    statement = select(Fighter).where(Fighter.name == name)
    existing = session.exec(statement).first()

    if existing:
        for key, value in data.items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    fighter = Fighter(name=name, **data)
    session.add(fighter)
    session.commit()
    session.refresh(fighter)
    return fighter
```

### JSON Fields

SQLite doesn't have a native array type. Store lists (like `signature_weapons` and
`fight_history`) as JSON-encoded strings. Encode on write, decode on read:

```python
import json

# Writing
profile.signature_weapons = json.dumps(["Left kick", "Elbow", "Clinch"])

# Reading
weapons: list[str] = json.loads(profile.signature_weapons)
```

### Database Errors

Wrap DB writes in try/except. SQLAlchemy raises `SQLAlchemyError` as the base class:

```python
from sqlalchemy.exc import SQLAlchemyError

try:
    session.add(record)
    session.commit()
except SQLAlchemyError as e:
    session.rollback()
    logger.error("Database write failed: %s", e)
    raise DatabaseError("Failed to save record") from e
```

Add `DatabaseError` to `server/exceptions.py`.

### Never Do This

```python
# WRONG — raw SQL string
session.exec("SELECT * FROM fighter WHERE name = ?", name)

# WRONG — creating sessions outside dependency injection
session = Session(engine)  # inside a route or business function

# WRONG — forgetting refresh after commit
session.commit()
return fighter  # fighter.id may be None — always refresh first
```

---

## Configuration and Secrets

All secrets and environment-specific config come from `.env` via `python-dotenv`.
Never hardcode credentials, URLs, or tokens.

Load config once in a `server/config.py` module and import it everywhere:

```python
# server/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    meta_access_token: str
    meta_instagram_account_id: str
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str
    r2_public_url: str
    database_url: str = "sqlite:///data/muaythai.db"

    class Config:
        env_file = ".env"

settings = Settings()
```

Use `pydantic-settings` — it validates that required keys are present at startup and
gives you a typed config object, not a bag of `os.getenv()` calls scattered everywhere.

---

## FastAPI Patterns

Use Pydantic models for all request and response bodies — not raw dicts.

```python
from pydantic import BaseModel

class GenerateRequest(BaseModel):
    fighter_name: str

class GenerateResponse(BaseModel):
    status: str
    card_path: str
    caption: str

@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    ...
```

Route handlers are thin. They validate input, call the pipeline, handle exceptions,
and return responses. They do not contain business logic.

```python
@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    try:
        raw = await fetcher.get_fighter_data(request.fighter_name)
        enriched = await enricher.enrich_fighter(raw)
        card_path = await renderer.render_card(enriched)
        return GenerateResponse(
            status="ok",
            card_path=card_path,
            caption=enriched.bio,
        )
    except FetchError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except EnrichmentError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except RenderError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Working with Claude (the API)

Build prompts as explicit strings — not f-string soup. Keep prompt text readable.

Always ask for structured JSON output and parse it with a proper schema, not string
manipulation.

```python
async def enrich_fighter(raw_data: FighterRawData) -> FighterProfile:
    prompt = f"""
    You are a Muay Thai analyst. Given the following fighter data, return a JSON object
    with this exact structure:

    {{
        "fighting_style": "string",
        "signature_weapons": ["string"],
        "attributes": {{
            "aggression": 1-10,
            "power": 1-10,
            "footwork": 1-10,
            "clinch": 1-10,
            "cardio": 1-10,
            "technique": 1-10
        }},
        "bio": "2-3 sentence narrative",
        "fun_fact": "string"
    }}

    Return only the JSON object. No markdown, no explanation.

    Fighter data:
    {json.dumps(raw_data.__dict__, indent=2)}
    """

    message = await client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        return parse_enrichment_response(message.content[0].text)
    except (json.JSONDecodeError, KeyError) as e:
        raise EnrichmentError("Failed to parse Claude response") from e
```

---

## Fetching Fighter Data

Fighter data comes from two public APIs — no HTML scraping.

**Wikipedia API** (`https://en.wikipedia.org/w/api.php`) — no key required.
Used for biographical text, career narrative, and fight history when structured data
isn't available elsewhere.

**TheSportsDB** (`https://www.thesportsdb.com/api/v1/json/3`) — free tier, no key needed.
Used for structured fields: nationality, team/gym, player ID.

Guidelines:
- Use `httpx.AsyncClient` for all requests — never `requests`
- Handle non-200 responses and empty result sets gracefully — raise `FetchError`, do not crash
- Prefer TheSportsDB structured fields over parsing Wikipedia text
- Fall back to Wikipedia when TheSportsDB returns no result for a fighter
- Log a warning (not an error) when a field can't be found — missing data is normal

---

## File Output

All generated files go in `output/`. Use timestamped filenames so nothing overwrites:

```python
from datetime import datetime

def make_output_path(fighter_name: str) -> Path:
    slug = fighter_name.lower().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("output") / f"{slug}_{timestamp}.png"
```

Use `pathlib.Path` everywhere. Never concatenate file paths with string operations.

---

## Code Style

- Format with `ruff format` — do not argue with the formatter
- Lint with `ruff check` — fix all warnings before committing
- Line length: 100 characters
- Imports: stdlib first, then third-party, then local — one blank line between groups
- No wildcard imports (`from module import *`)
- Docstrings on every public function — one line summary, then Args/Returns if non-obvious

---

## What Not to Do

- No `print()` — use logging
- No bare `except:` — always catch specific exceptions
- No `os.getenv()` scattered through modules — use `config.settings`
- No synchronous `requests` library — use `httpx` async
- No string path concatenation — use `pathlib.Path`
- No raw dict returns from functions with complex shapes — use dataclasses or TypedDicts
- No business logic in route handlers
- No secrets in code, ever
- No raw SQL strings — use SQLModel `select()`
- No DB sessions created outside of `get_session()` dependency injection
- No forgetting `session.refresh()` after `session.commit()` — you will get `None` IDs
- No storing lists or dicts directly in DB columns — JSON-encode them first
- No bare `session.rollback()` without logging the error first
