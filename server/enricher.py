import logging
from typing import Any

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

    TODO:
    - Import settings from server.config and initialize an Anthropic client
    - Build a prompt that includes json.dumps(raw_data, indent=2)
    - Ask Claude to return a JSON object with the exact structure above
    - Specify "Return only the JSON object. No markdown, no explanation."
    - Call client.messages.create() with model="claude-opus-4-5", max_tokens=1024
    - Parse the JSON response with json.loads()
    - Raise EnrichmentError if json.JSONDecodeError or a required key is missing
    - Return the parsed dict
    """
    logger.info("Enriching fighter data for: %s", raw_data.get("name"))

    # TODO: implement Claude enrichment
    return {
        "name": raw_data.get("name", "Unknown"),
        "nickname": raw_data.get("nickname"),
        "nationality": raw_data.get("nationality"),
        "gym": raw_data.get("gym"),
        "record_wins": raw_data.get("record_wins"),
        "record_losses": raw_data.get("record_losses"),
        "record_kos": raw_data.get("record_kos"),
        "fighting_style": "TODO: implement enrichment",
        "signature_weapons": ["TODO"],
        "attributes": {
            "aggression": 0,
            "power": 0,
            "footwork": 0,
            "clinch": 0,
            "cardio": 0,
            "technique": 0,
        },
        "bio": "TODO: implement enrichment",
        "fun_fact": "TODO: implement enrichment",
    }
