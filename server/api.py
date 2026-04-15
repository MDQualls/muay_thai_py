import logging
from contextlib import asynccontextmanager
from typing import Any
from pathlib import Path
from datetime import datetime, UTC
import json

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import Session, select, desc
from server.models import Fighter, FighterProfile, Card, InstagramPost

from server import enricher, fetcher, publisher, renderer, uploader, caption_builder
from server.database import create_db_and_tables, get_session
from server.exceptions import EnrichmentError, FetchError, PublishError, RenderError, UploadError

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
    card_paths: list[str]   # was: card_path: str
    caption: str


class PostRequest(BaseModel):
    caption: str | None = None


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
    """
    try:
        logger.info("Generating card for fighter: %s", request.fighter_name)

        raw_data = await fetcher.get_fighter_data(request.fighter_name)
        enriched_data = await enricher.enrich_fighter(raw_data)
        card_paths = await renderer.render_carousel(enriched_data)
        caption = caption_builder.build_caption(enriched_data)

        # Upsert Fighter
        statement = select(Fighter).where(Fighter.name == enriched_data.get("name"))
        fighter = session.exec(statement).first()

        if fighter:
            fighter.nickname = enriched_data.get("nickname")
            fighter.nationality = enriched_data.get("nationality")
            fighter.gym = enriched_data.get("gym")
            fighter.record_wins = enriched_data.get("record_wins")
            fighter.record_losses = enriched_data.get("record_losses")
            fighter.record_kos = enriched_data.get("record_kos")
            fighter.wikipedia_url = raw_data.get("wikipedia_url")
            fighter.updated_at = datetime.now(UTC)
            session.add(fighter)
        else:
            fighter = Fighter(
                name=enriched_data.get("name"),
                nickname=enriched_data.get("nickname"),
                nationality=enriched_data.get("nationality"),
                gym=enriched_data.get("gym"),
                record_wins=enriched_data.get("record_wins"),
                record_losses=enriched_data.get("record_losses"),
                record_kos=enriched_data.get("record_kos"),
                wikipedia_url=raw_data.get("wikipedia_url"),
            )
            session.add(fighter)

        session.commit()
        session.refresh(fighter)

        profile = FighterProfile(
            fighter_id=fighter.id,
            fighting_style=enriched_data.get("fighting_style", ""),
            signature_weapons=json.dumps(enriched_data.get("signature_weapons", [])),
            attr_aggression=enriched_data["attributes"]["aggression"],
            attr_power=enriched_data["attributes"]["power"],
            attr_footwork=enriched_data["attributes"]["footwork"],
            attr_clinch=enriched_data["attributes"]["clinch"],
            attr_cardio=enriched_data["attributes"]["cardio"],
            attr_technique=enriched_data["attributes"]["technique"],
            bio=enriched_data.get("bio", ""),
            fun_fact=enriched_data.get("fun_fact"),
            career_highlight=enriched_data.get("career_highlight"),
            hashtags=json.dumps(enriched_data.get("hashtags", [])),
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)

        for card_path in card_paths:
            card = Card(
                fighter_id=fighter.id,
                profile_id=profile.id,
                local_path=str(card_path),
                caption=caption,
            )
            session.add(card)
        session.commit()

        return GenerateResponse(
            status="ok",
            card_paths=[str(p) for p in card_paths],
            caption=caption,
        )
    except FetchError as e:
        logger.error("Data fetch failed for %s: %s", request.fighter_name, e)
        raise HTTPException(status_code=502, detail=str(e))
    except EnrichmentError as e:
        logger.error("Enrichment failed for %s: %s", request.fighter_name, e)
        raise HTTPException(status_code=502, detail=str(e))
    except RenderError as e:
        logger.error("Render failed for %s: %s", request.fighter_name, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/preview")
async def preview(session: Session = Depends(get_session)) -> FileResponse:
    """Return the most recently generated slide 1 as a preview image."""
    latest_card = session.exec(
        select(Card).order_by(desc(Card.created_at))
    ).first()

    if not latest_card:
        raise HTTPException(status_code=404, detail="No card generated yet")

    card_path = Path(latest_card.local_path)
    if not card_path.exists():
        raise HTTPException(status_code=404, detail="Card file not found on disk")

    return FileResponse(str(card_path), media_type="image/jpeg")

@app.post("/post", response_model=PostResponse)
async def post(
    request: PostRequest,
    session: Session = Depends(get_session),
) -> PostResponse:
    """Upload the latest card to R2 and post it to Instagram.
    """
    try:
        # Get the most recent set of cards — the 3 slides from the last generate run
        # Cards are created in a batch so they share the same profile_id
        # Get the latest profile_id and fetch all cards for it
        latest_card = session.exec(
            select(Card).order_by(desc(Card.created_at))
        ).first()

        if not latest_card:
            raise HTTPException(status_code=400, detail="No cards generated yet.")

        cards = session.exec(
            select(Card).where(Card.profile_id == latest_card.profile_id)
        ).all()

        card_paths = [Path(card.local_path) for card in cards]
        caption = caption = request.caption or latest_card.caption or ""
        image_urls = await uploader.upload_carousel(card_paths)
        instagram_post_id = await publisher.post_carousel(image_urls, caption)

        for i, card in enumerate(cards):
            card.r2_url = image_urls[i]
            session.add(card)

            post_record = InstagramPost(
                card_id=card.id,
                instagram_id=instagram_post_id,
                caption_used=caption,
            )
            session.add(post_record)

        session.commit()

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
    """
    fighters = session.exec(select(Fighter)).all()
    return [f.model_dump() for f in fighters]


@app.get("/fighters/{fighter_id}/cards")
async def get_fighter_cards(
    fighter_id: int,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Return all cards for a given fighter, including R2 URL and post status.
    """
    cards = session.exec(select(Card).where(Card.fighter_id == fighter_id)).all()
    return [c.model_dump() for c in cards]
