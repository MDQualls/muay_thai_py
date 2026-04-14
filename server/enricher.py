import logging
import anthropic
import json
from server.service.enrich.enrichment_handler import EnrichmentHandler
from server.service.enrich.prompter import Prompter
from typing import Any
from server.config import settings
from server.exceptions import EnrichmentError

logger = logging.getLogger(__name__)


async def enrich_fighter(raw_data: dict[str, Any]) -> dict[str, Any]:
    """Send raw fighter data to Claude and get back a structured enrichment.

    Args:
        raw_data: dict returned from scraper.get_fighter_data()

    Returns:
        dict with keys:
            fighting_style: str (e.g. "Aggressive pressure fighter")
            signature_weapons: list[str] (e.g. ["Left body kick", "Elbow", "Clinch"])
            attributes: dict with int scores 1-10 for:
                aggression, power, footwork, clinch, cardio, technique
            bio: str (2-3 sentence punchy narrative)
            fun_fact: str
    """

    logger.info("Enriching fighter data for: %s", raw_data.get("name"))

    extract = raw_data.get("wikipedia_extract", "")

    if not extract:
        msg = "Failed to extract the Wikipedia content for the enricher"
        logger.warning(msg)
        raise ValueError(msg)

    handler = EnrichmentHandler()
    message = await handler.enrich(extract)
    
    try:
        text = message.content[0].text.strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude response as JSON: %s", e)
        raise EnrichmentError(f"Claude returned invalid JSON: {e}") from e