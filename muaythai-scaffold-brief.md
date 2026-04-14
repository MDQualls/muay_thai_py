# Claude Code Brief: Muay Thai Fighter Card App — Docker Scaffold & Project Setup

## What This Is

A local web app that generates stylized Muay Thai fighter profile cards and posts them to Instagram. The app runs in Docker, is accessed at `localhost:8000`, and is built in Python with FastAPI on the backend and a simple HTML/CSS/JS frontend.

**Important:** This brief is for scaffolding only. Do not implement business logic. The goal is a clean, well-structured starting point where the developer can write the actual code themselves. Stub out functions with `pass` or placeholder returns. Leave TODO comments everywhere logic needs to be added.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.12 |
| Package manager | `uv` |
| Web framework | FastAPI + Uvicorn |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| Card rendering | Jinja2 + Playwright (Chromium) |
| AI enrichment | Anthropic SDK (Claude) |
| Image processing | `rembg` |
| HTTP client | `httpx` |
| HTML parsing | `BeautifulSoup4` |
| Instagram posting | Meta Graph API via `httpx` |
| Image hosting | Cloudflare R2 via `boto3` |
| Database | SQLite via SQLModel |
| Containerization | Docker + Docker Compose |
| Config/secrets | `python-dotenv` |

---

## Project Structure to Scaffold

```
muaythai-cards/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── main.py
├── server/
│   ├── __init__.py
│   ├── api.py
│   ├── database.py
│   ├── models.py
│   ├── scraper.py
│   ├── enricher.py
│   ├── renderer.py
│   ├── uploader.py
│   └── publisher.py
├── templates/
│   └── card.html
├── ui/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── assets/
│   └── fonts/
│       └── .gitkeep
└── output/
    └── .gitkeep
```

---

## Dockerfile Requirements

- Base image: `mcr.microsoft.com/playwright/python:v1.44.0-jammy` — this includes Python and Chromium/Playwright dependencies pre-installed
- Install `uv` inside the container
- Use `uv` to install dependencies from `pyproject.toml`
- Run `playwright install chromium` as part of the build
- Working directory: `/app`
- Expose port `8000`
- Start command: `uvicorn server.api:app --host 0.0.0.0 --port 8000 --reload`

---

## docker-compose.yml Requirements

- Single service: `app`
- Build from local Dockerfile
- Port mapping: `8000:8000`
- Mount volumes:
  - `.:/app` — for hot reload (source code)
  - `./output:/app/output` — so generated card JPEGs persist outside the container
  - `./data:/app/data` — so the SQLite database file persists outside the container
- Load env from `.env` file
- Restart policy: `unless-stopped`

---

## pyproject.toml Requirements

Use `uv` format. Dependencies to include:

```
fastapi
uvicorn[standard]
httpx
beautifulsoup4
playwright
anthropic
jinja2
rembg
pillow
boto3
python-dotenv
sqlmodel
pydantic-settings
```

---

## .env.example

Include placeholder keys for:

```
ANTHROPIC_API_KEY=
META_ACCESS_TOKEN=
META_INSTAGRAM_ACCOUNT_ID=
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_URL=
DATABASE_URL=sqlite:///data/muaythai.db
```

---

## main.py

Entry point. Should:
- Start the FastAPI app via uvicorn programmatically
- Open `http://localhost:8000` in the default browser using `webbrowser.open()`
- Include a comment explaining this file is only used for local dev outside Docker; inside Docker, uvicorn is called directly

---

## server/api.py

FastAPI app with the following routes stubbed out. Each route should return a placeholder JSON response and include a TODO comment.

### Routes

**`GET /`**
Serve `ui/index.html` using `FileResponse`

**`GET /static/{path}`**
Serve static files from the `ui/` directory

**`POST /generate`**
Accept JSON body: `{ "fighter_name": "string" }`
Pipeline stub — should call (in order):
1. `scraper.get_fighter_data(fighter_name)` 
2. `enricher.enrich_fighter(raw_data)`
3. `renderer.render_card(enriched_data)`

Return: `{ "status": "ok", "card_path": "output/card.jpg", "caption": "..." }`

**`GET /preview`**
Return the most recently generated card JPEG as a `FileResponse`

**`POST /post`**
Accept JSON body: `{ "caption": "string" }`
Should call:
1. `uploader.upload_card(card_path)`
2. `publisher.post_to_instagram(image_url, caption)`

Return: `{ "status": "posted", "instagram_post_id": "..." }`

---

## server/models.py

This is the one module Claude Code should implement fully — not stub. Generate the complete
SQLModel schema. The developer will tweak it, but wants a working starting point.

Define the following SQLModel table classes:

**`Fighter`** — one row per unique fighter ever processed

```
id              int         primary key, auto
name            str         indexed
nickname        str | None
nationality     str | None
gym             str | None
record_wins     int | None
record_losses   int | None
record_kos      int | None
sportsdb_id    str | None
wikipedia_url   str | None
created_at      datetime    default now
updated_at      datetime    default now, updated on save
```

**`FighterProfile`** — Claude's enriched analysis. One per enrichment run (a fighter can
have multiple over time as their career evolves).

```
id                  int         primary key, auto
fighter_id          int         foreign key → Fighter.id
fighting_style      str
signature_weapons   str         JSON-encoded list e.g. '["Left kick", "Elbow"]'
attr_aggression     int         1-10
attr_power          int         1-10
attr_footwork       int         1-10
attr_clinch         int         1-10
attr_cardio         int         1-10
attr_technique      int         1-10
bio                 str
fun_fact            str | None
created_at          datetime    default now
```

**`Card`** — one row per generated card JPEG

```
id              int         primary key, auto
fighter_id      int         foreign key → Fighter.id
profile_id      int         foreign key → FighterProfile.id
local_path      str         path to JPEG in output/
r2_url          str | None  populated after upload
caption         str | None  Claude-generated caption
created_at      datetime    default now
```

**`InstagramPost`** — one row per successful Instagram post

```
id              int         primary key, auto
card_id         int         foreign key → Card.id
instagram_id    str         the post ID returned by Meta Graph API
posted_at       datetime    default now
caption_used    str         the final caption that was actually posted
```

Include all SQLModel imports, proper `Optional` typing, and `Field()` definitions.
Add a `fight_history` JSON field to `Fighter` as a `str | None` (JSON-encoded list)
for storing raw fight history from the scraper.

---

## server/database.py

```python
def get_engine():
    """
    TODO:
    - Create SQLModel engine from DATABASE_URL in config
    - Use check_same_thread=False for SQLite (required for FastAPI)
    - Return the engine
    """
    pass

def create_db_and_tables():
    """
    TODO:
    - Call SQLModel.metadata.create_all(engine)
    - Called once at app startup from api.py lifespan
    """
    pass

def get_session():
    """
    FastAPI dependency that yields a database session.
    
    TODO:
    - Use Session(engine) as a context manager
    - Yield the session
    - Used as: session: Session = Depends(get_session)
    """
    pass
```

---

## server/api.py — Updated Route Notes

The `/generate` route should also:
- After a successful generate, check if this fighter already exists in the DB
  (look up by name) and upsert the Fighter row
- Save the FighterProfile row linked to the Fighter
- Save the Card row with the local JPEG path
- TODO comments for each of these steps — the developer will write the actual DB calls

The `/post` route should also:
- After a successful Instagram post, save an InstagramPost row
- TODO comment for this step

Add `session: Session = Depends(get_session)` to route signatures so the DB
dependency is wired and ready for the developer to use.

Add a `GET /fighters` route that returns all Fighter rows from the database as JSON.
This gives the developer a way to verify data is being saved.

Add a `GET /fighters/{fighter_id}/cards` route that returns all Card rows for a
given fighter, including their R2 URL and post status.

---

## data/ directory

Add `data/` to the project structure with a `.gitkeep`. The SQLite file
(`muaythai.db`) will be created here at runtime and persists via the Docker volume.
Add `data/*.db` to `.gitignore`.

---

## server/scraper.py

```python
def get_fighter_data(fighter_name: str) -> dict:
    """
    Fetch fiter data from Wikipedia and SportsDB.
    
    TODO:
    - Search Wikipedia for the fighter
    - Extract: record (W/L/KO), fight history, gym, nationality
    - Search ONE Championship site for additional data
    - Return raw combined dict
    
    Args:
        fighter_name: Fighter's full name e.g. "Rodtang Jitmuangnon"
    
    Returns:
        dict with keys: name, nickname, record, gym, nationality,
                        fight_history, notable_wins
    """
    pass
```

---

## server/enricher.py

```python
def enrich_fighter(raw_data: dict) -> dict:
    """
    Send raw fighter data to Claude and get back structured enrichment.
    
    TODO:
    - Build a prompt that includes the raw_data
    - Ask Claude to return JSON with:
        - fighting_style: str (e.g. "Aggressive pressure fighter")
        - signature_weapons: list[str] (e.g. ["Left body kick", "Elbow", "Clinch"])
        - attributes: dict with scores 1-10 for:
            aggression, power, footwork, clinch, cardio, technique
        - bio: str (2-3 sentence punchy narrative)
        - fun_fact: str
    - Parse and return the JSON response
    
    Args:
        raw_data: dict returned from scraper.get_fighter_data()
    
    Returns:
        dict with enriched fighter profile
    """
    pass
```

---

## server/renderer.py

```python
def render_card(enriched_data: dict) -> str:
    """
    Render the fighter card HTML template and screenshot to JPEG via Playwright.
    
    TODO:
    - Load templates/card.html using Jinja2
    - Inject enriched_data into template
    - Launch Playwright (Chromium, headless)
    - Navigate to rendered HTML
    - Screenshot to output/card.jpg at 1080x1080
    - Return path to the JPEG
    
    Args:
        enriched_data: dict returned from enricher.enrich_fighter()
    
    Returns:
        str path to generated JPEG e.g. "output/card.jpg"
    """
    pass
```

---

## server/uploader.py

```python
def upload_card(card_path: str) -> str:
    """
    Upload the card JPEG to Cloudflare R2 and return a public URL.
    
    TODO:
    - Use boto3 with R2 credentials from env
    - Upload card_path to R2_BUCKET_NAME
    - Filename should be timestamped e.g. card_20240101_120000.jpg
    - Return the public URL using R2_PUBLIC_URL + filename
    
    Args:
        card_path: Local path to the card JPEG
    
    Returns:
        str public URL to the uploaded image
    """
    pass
```

---

## server/publisher.py

```python
def post_to_instagram(image_url: str, caption: str) -> str:
    """
    Post an image to Instagram via the Meta Graph API.
    
    TODO:
    Step 1 - Create media container:
        POST https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media
        params: image_url, caption, access_token
        Returns a container ID

    Step 2 - Publish the container:
        POST https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish
        params: creation_id (container ID), access_token
        Returns the post ID
    
    Args:
        image_url: Public URL to the card image (from uploader)
        caption: Instagram caption text
    
    Returns:
        str Instagram post ID
    """
    pass
```

---

## templates/card.html

Scaffold a basic 1080x1080px HTML card template. Use dark background (#1a1a2e or similar). Include Jinja2 template variables as placeholders:

- `{{ fighter.name }}`
- `{{ fighter.nickname }}`
- `{{ fighter.record }}`
- `{{ fighter.nationality }}`
- `{{ fighter.gym }}`
- `{{ fighter.fighting_style }}`
- `{{ fighter.bio }}`
- `{{ fighter.signature_weapons }}` (loop)
- `{{ fighter.attributes }}` (loop for stat bars)

Style it to look like a real fighter stat card — dark background, bold typography, colored accent bars for attributes. Use Google Fonts (Oswald or Bebas Neue for headings). This is just a starting scaffold — the developer will iterate on the design.

---

## ui/index.html

A clean, minimal single-page app UI. Dark theme to match the card aesthetic. Should include:

- App title / header
- A text input for fighter name with a "Generate" button
- A status/progress area that shows pipeline steps (initially hidden)
- A card preview area (img tag, initially hidden)
- A caption textarea (initially hidden, editable)
- A "Post to Instagram" button (initially hidden)
- A success/error message area

No framework. Vanilla HTML. Link to `app.js` and `styles.css`.

---

## ui/app.js

Stub out the frontend logic with TODO comments:

```javascript
// TODO: on Generate button click
//   - show progress area
//   - POST to /generate with fighter_name
//   - poll or await response
//   - on success: show card preview (GET /preview), show caption, show Post button

// TODO: on Post button click
//   - POST to /post with caption text
//   - show success message with post ID
```

---

## ui/styles.css

Basic dark theme styles. Clean, minimal. Just enough to make the UI look intentional — not bare HTML defaults.

---

## README.md

Include:
- Project description (one paragraph)
- Prerequisites (Docker Desktop, a `.env` file)
- Setup instructions:
  1. Copy `.env.example` to `.env` and fill in keys
  2. `docker compose up --build`
  3. Open `http://localhost:8000`
- Brief description of each module in `server/`
- Note that `main.py` is for running outside Docker only

---

## .gitignore

Standard Python gitignore plus:
- `.env`
- `output/*.jpg`
- `__pycache__`
- `.DS_Store`

---

## Final Instructions for Claude Code

1. Scaffold every file listed above. Do not skip any.
2. Do not implement any business logic. Stub everything with `pass`, placeholder returns, and TODO comments — **except** `server/models.py`, which should be fully implemented with complete SQLModel table definitions.
3. The Dockerfile and docker-compose.yml should be fully functional and ready to run — these are not stubs.
4. The FastAPI routes in `api.py` should be fully wired (imports, route decorators, function calls to stubs, DB session dependency injection) — they just won't return real data yet.
5. The UI should render correctly in a browser — not just an empty page.
6. Create the `data/` directory with a `.gitkeep` and ensure it is volume-mounted in docker-compose.
7. Call `create_db_and_tables()` in the FastAPI lifespan so the schema is created automatically on first run.
8. After scaffolding, run `docker compose build` to confirm the image builds without errors.
9. Confirm the app starts and `http://localhost:8000` serves the UI.
10. Confirm `http://localhost:8000/fighters` returns an empty JSON array (not an error) — this verifies the DB is initialized and the route is wired.
