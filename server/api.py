import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import Session

from server import enricher, publisher, renderer, scraper, uploader
from server.database import create_db_and_tables, get_session
from server.exceptions import EnrichmentError, PublishError, RenderError, ScraperError, UploadError

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database schema on startup."""
    create_db_and_tables()
    logger.info("Database initialized")
    yield


app = FastAPI(title="Muay Thai Fighter Card App", lifespan=lifespan)

# Serve static files (JS, CSS) from the ui/ directory
app.mount("/static", StaticFiles(directory="ui"), name="static")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    fighter_name: str


class GenerateResponse(BaseModel):
    status: str
    card_path: str
    caption: str


class PostRequest(BaseModel):
    caption: str


class PostResponse(BaseModel):
    status: str
    instagram_post_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
async def index() -> FileResponse:
    """Serve the frontend SPA."""
    return FileResponse("ui/index.html")


@app.post("/generate", response_model=GenerateResponse)
async def generate(
    request: GenerateRequest,
    session: Session = Depends(get_session),
) -> GenerateResponse:
    """Run the full fighter card pipeline: scrape → enrich → render.

    TODO (after stubs are implemented):
    - Upsert a Fighter row for request.fighter_name
    - Save a FighterProfile row linked to the Fighter
    - Save a Card row with the local PNG path
    """
    try:
        logger.info("Generating card for fighter: %s", request.fighter_name)

        raw_data = await scraper.get_fighter_data(request.fighter_name)
        enriched_data = await enricher.enrich_fighter(raw_data)
        card_path = await renderer.render_card(enriched_data)

        # TODO: upsert Fighter row in DB
        # TODO: save FighterProfile row linked to fighter
        # TODO: save Card row with local_path=card_path

        return GenerateResponse(
            status="ok",
            card_path=card_path,
            caption=enriched_data.get("bio", ""),
        )
    except ScraperError as e:
        logger.error("Scraper failed for %s: %s", request.fighter_name, e)
        raise HTTPException(status_code=502, detail=str(e))
    except EnrichmentError as e:
        logger.error("Enrichment failed for %s: %s", request.fighter_name, e)
        raise HTTPException(status_code=502, detail=str(e))
    except RenderError as e:
        logger.error("Render failed for %s: %s", request.fighter_name, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/preview")
async def preview() -> FileResponse:
    """Return the most recently generated card PNG.

    TODO:
    - Query the Card table for the most recent row (order by created_at DESC)
    - Return FileResponse(card.local_path)
    - Raise 404 if no cards have been generated yet
    """
    # Placeholder — returns a 404 until implemented
    raise HTTPException(status_code=404, detail="No card generated yet")


@app.post("/post", response_model=PostResponse)
async def post(
    request: PostRequest,
    session: Session = Depends(get_session),
) -> PostResponse:
    """Upload the latest card to R2 and post it to Instagram.

    TODO (after stubs are implemented):
    - Query DB for the most recent Card row to get local_path
    - After successful post, save an InstagramPost row linked to the Card
    """
    try:
        # TODO: get latest card_path from DB
        card_path = "output/card.png"  # placeholder

        image_url = await uploader.upload_card(card_path)
        instagram_post_id = await publisher.post_to_instagram(image_url, request.caption)

        # TODO: save InstagramPost row to DB

        return PostResponse(status="posted", instagram_post_id=instagram_post_id)
    except UploadError as e:
        logger.error("Upload failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except PublishError as e:
        logger.error("Instagram publish failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/fighters")
async def list_fighters(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """Return all fighters from the database.

    TODO:
    - Use session.exec(select(Fighter)).all()
    - Return the list of Fighter rows
    """
    # Placeholder — returns empty list until DB is fully wired
    return []


@app.get("/fighters/{fighter_id}/cards")
async def get_fighter_cards(
    fighter_id: int,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Return all cards for a given fighter, including R2 URL and post status.

    TODO:
    - Use session.exec(select(Card).where(Card.fighter_id == fighter_id)).all()
    - For each card, also check if an InstagramPost row exists
    - Return the list of card dicts
    """
    # Placeholder — returns empty list until DB is fully wired
    return []
