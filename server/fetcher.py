import logging
from typing import Any

logger = logging.getLogger(__name__)

# Wikipedia REST API — no key required
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"

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

    TODO — Wikipedia API:
    - Use httpx.AsyncClient for all requests
    - Search for the fighter's Wikipedia page:
        GET {WIKIPEDIA_API_URL}
        params: action=query, list=search, srsearch=fighter_name, format=json
    - Take the first result's pageid, then fetch the full page summary:
        GET {WIKIPEDIA_API_URL}
        params: action=query, pageids={pageid}, prop=extracts, exintro=True,
                explaintext=True, format=json
    - Parse the extract text for: nickname, nationality, gym, record

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

    # TODO: implement Wikipedia + SportsDB fetching
    return {
        "name": fighter_name,
        "nickname": None,
        "record_wins": None,
        "record_losses": None,
        "record_kos": None,
        "gym": None,
        "nationality": None,
        "fight_history": [],
        "notable_wins": [],
        "wikipedia_url": None,
        "sportsdb_id": None,
    }
