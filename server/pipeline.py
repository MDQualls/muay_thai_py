import json
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from server import caption_builder, enricher, fetcher, publisher, renderer, uploader
from server.models import Card, Fighter, FighterProfile, InstagramPost

logger = logging.getLogger(__name__)


def save_generation(
    session: Session,
    raw_data: dict[str, Any],
    enriched_data: dict[str, Any],
    card_paths: list[Path],
    caption: str,
) -> tuple[Fighter, FighterProfile, list[Card]]:
    """Upsert Fighter, insert FighterProfile and Cards into DB.

    Args:
        session: Active database session (injected or managed by caller).
        raw_data: Raw fighter data from fetcher.
        enriched_data: Enriched data from enricher.
        card_paths: Paths to rendered JPEG slides.
        caption: Instagram caption text.

    Returns:
        Tuple of (Fighter, FighterProfile, list[Card]) — all refreshed after commit.
    """
    fighter = session.exec(
        select(Fighter).where(Fighter.name == enriched_data.get("name"))
    ).first()

    if fighter:
        fighter.nickname = enriched_data.get("nickname")
        fighter.nationality = enriched_data.get("nationality")
        fighter.gym = enriched_data.get("gym")
        fighter.record_wins = enriched_data.get("record_wins")
        fighter.record_losses = enriched_data.get("record_losses")
        fighter.record_kos = enriched_data.get("record_kos")
        fighter.record_draws = enriched_data.get("record_draws")
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
            record_draws=enriched_data.get("record_draws"),
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
        recent_results=json.dumps(enriched_data.get("recent_results", [])),
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)

    cards = []
    for card_path in card_paths:
        card = Card(
            fighter_id=fighter.id,
            profile_id=profile.id,
            local_path=str(card_path),
            caption=caption,
        )
        session.add(card)
        cards.append(card)
    session.commit()
    for card in cards:
        session.refresh(card)

    return fighter, profile, cards


async def run_full_pipeline(fighter_name: str) -> dict[str, Any]:
    """Run the complete generate + post pipeline headlessly.

    Fetches, enriches, renders, saves to DB, uploads to R2, and publishes to Instagram.
    Manages its own database session internally.

    Args:
        fighter_name: The fighter's name to process.

    Returns:
        dict with 'fighter_name' and 'instagram_post_id'.

    Raises:
        FetchError, EnrichmentError, RenderError, UploadError, PublishError
    """
    from server.database import create_session

    raw_data = await fetcher.get_fighter_data(fighter_name)
    enriched_data = await enricher.enrich_fighter(raw_data)
    card_paths = await renderer.render_carousel(enriched_data)
    caption_text = caption_builder.build_caption(enriched_data)

    with create_session() as session:
        _, _, cards = save_generation(session, raw_data, enriched_data, card_paths, caption_text)

        upload_paths = [Path(card.local_path) for card in cards]
        image_urls = await uploader.upload_carousel(upload_paths)
        instagram_post_id = await publisher.post_carousel(image_urls, caption_text)

        for i, card in enumerate(cards):
            card.r2_url = image_urls[i]
            session.add(card)
            post_record = InstagramPost(
                card_id=card.id,
                instagram_id=instagram_post_id,
                caption_used=caption_text,
            )
            session.add(post_record)
        session.commit()

    return {"fighter_name": fighter_name, "instagram_post_id": instagram_post_id}
