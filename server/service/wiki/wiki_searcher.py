import httpx
import logging
import server.constants
import server.exceptions
from typing import Any

class WikiSearcher:

    PARAMS = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": ""
    }

    def __init__(self, fighter_name: str) -> None:

        self.logger = logging.getLogger(__name__)

        if not fighter_name or not fighter_name.strip():
            msg = "Failed to pass fighter name to get_fighter_data"
            self.logger.warning(msg)
            raise ValueError(msg)
        
        self.fighter_name = fighter_name

    async def do_wiki_search(self) -> dict[str, Any]:

        params = {**self.PARAMS, "srsearch": self.fighter_name}

        try:
            async with httpx.AsyncClient(headers=server.constants.WIKIPEDIA_HEADERS) as client:
                response = await client.get(server.constants.WIKIPEDIA_URL, params=params)
        except httpx.RequestError as e:
            self._handle_fetch_exception(f"Network error reaching Wikipedia: {e}")

        if response.status_code != 200:
            self._handle_fetch_exception(f"Wikipedia returned {response.status_code} for {self.fighter_name}")
        
        results = response.json().get("query", {}).get("search", [])

        if not results:
            self._handle_fetch_exception(f"No Wikipedia article found for '{self.fighter_name}'")

        top_result = results[0]

        name_words = [w for w in self.fighter_name.lower().split() if len(w) > 2]
        title_lower = top_result["title"].lower()
        if not any(word in title_lower for word in name_words):
            self._handle_fetch_exception(f"No relevant Wikipedia article found for '{self.fighter_name}'")
        
        return {
            "title": top_result["title"],
            "page_id": top_result["pageid"]
        }
    
    def _handle_fetch_exception(self, msg: str) -> None:
        self.logger.warning(msg)
        raise server.exceptions.FetchError(msg)

