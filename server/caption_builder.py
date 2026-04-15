from typing import Any
import logging

logger = logging.getLogger(__name__)

def build_caption(enriched_data: dict[str, Any]) -> str:
    """Build an Instagram caption from enriched fighter data.

    Args:
        enriched_data: dict returned from enricher.enrich_fighter()

    Returns:
        str caption with bio and hashtags
    """

    logger.info("Building caption for Instagram post")

    bio = enriched_data.get("bio", "")
    
    # Fighter-specific tags from Claude
    fighter_tags = enriched_data.get("hashtags", [])
    
    # Always-on base tags
    base_tags = ["MuayThaiCards", "MuayThai", "FightSport"]
    
    all_tags = fighter_tags + [t for t in base_tags if t not in fighter_tags]
    hashtag_string = " ".join(f"#{tag}" for tag in all_tags)
    
    return f"{bio}\n\n{hashtag_string}"