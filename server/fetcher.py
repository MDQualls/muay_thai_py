import logging
import asyncio
from typing import Any
from server.service.wiki.wiki_searcher import WikiSearcher

logger = logging.getLogger(__name__)


# TheSportsDB — free tier uses key "3"
SPORTSDB_API_URL = "https://www.thesportsdb.com/api/v1/json/3"


async def get_fighter_data(fighter_name: str) -> dict[str, Any]:
    """Fetch fighter data from the Wikipedia API and TheSportsDB API.

    Args:
        fighter_name: Fighter's full name e.g. "Rodtang Jitmuangnon"

    Returns:
        dict with keys: name, nickname, record_wins, record_losses, record_kos,
                        gym, nationality, fight_history, notable_wins,
                        wikipedia_url, sportsdb_id

    TODO — TheSportsDB API:
    - Search for the fighter by name:
        GET {SPORTSDB_API_URL}/searchplayers.php?p={fighter_name}
    - If a result is found, extract structured fields:
        strPlayer, strNationality, strTeam, strDescriptionEN
    - strDescriptionEN often contains career narrative and fight history

    TODO — Merging:
    - Prefer SportsDB structured fields (nationality, team/gym) over Wikipedia text parsing
    - Fall back to Wikipedia when SportsDB returns no result
    - If neither source has data for a field, leave it as None — do not guess
    - Raise FetchError on HTTP errors (non-200 responses), do not crash silently
    """

    logger.info("Fetching fighter data for: %s", fighter_name)

    try:
        searcher = WikiSearcher(fighter_name)
        r = await searcher.do_wiki_search()
    except Exception as e:
        raise e
    
    return {
        "name": fighter_name,
        "wikipedia_extract": r,        
    }
