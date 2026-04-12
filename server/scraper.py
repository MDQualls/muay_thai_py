import logging
from typing import Any

logger = logging.getLogger(__name__)

# Polite scraper headers — always identify the client
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


async def get_fighter_data(fighter_name: str) -> dict[str, Any]:
    """Scrape fighter data from Tapology and ONE Championship.

    Args:
        fighter_name: Fighter's full name e.g. "Rodtang Jitmuangnon"

    Returns:
        dict with keys: name, nickname, record_wins, record_losses, record_kos,
                        gym, nationality, fight_history, notable_wins,
                        tapology_url, one_champ_url

    TODO:
    - Use httpx.AsyncClient with HEADERS for all requests
    - Search Tapology for the fighter name, follow the first result link
    - Extract: record (W/L/KO), fight history, gym, nationality, nickname
    - Search ONE Championship site for additional profile data
    - Add asyncio.sleep(1) between requests to be polite
    - Handle 404s and non-200 responses — raise ScraperError, do not crash
    - Return the combined raw dict
    """
    logger.info("Scraping fighter data for: %s", fighter_name)

    # TODO: implement scraping
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
        "tapology_url": None,
        "one_champ_url": None,
    }
