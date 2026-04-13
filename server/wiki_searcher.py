import httpx
import logging
import server.constants
import server.exceptions

class WikiSearcher:

    URL = "https://en.wikipedia.org/w/api.php"

    PARAMS = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": ""
    }

    def __init__(self, fighter_name: str):

        self.logger = logging.getLogger(__name__)

        if not fighter_name or not fighter_name.strip():
            msg = "Failed to pass fighter name to get_fighter_data"
            self.logger.warning(msg)
            raise ValueError(msg)
        
        self.fighter_name = fighter_name

    async def do_wiki_search(self) -> dict[str, any]:

        params = {**self.PARAMS, "srsearch": self.fighter_name}

        async with httpx.AsyncClient(headers=server.constants.HEADERS) as client:
            response = await client.get(self.URL, params=params)

        if response.status_code != 200:
            self._handle_fetch_exception(f"Wikipedia returned {response.status_code} for {self.fighter_name}")
        
        results = response.json().get("query", {}).get("search", [])

        if not results:
            self._handle_fetch_exception(f"No Wikipedia article found for '{self.fighter_name}'")

        top_result = results[0]

        if self.fighter_name.lower().split()[0] not in top_result["title"].lower():
            self._handle_fetch_exception(f"No relevant Wikipedia article found for '{self.fighter_name}'")
        
        return {
            "title": top_result["title"],
            "page_id": top_result["pageid"]
        }
    
    def _handle_fetch_exception(self, msg: str):
        self.logger.warning(msg)
        raise server.exceptions.FetchError(msg)

