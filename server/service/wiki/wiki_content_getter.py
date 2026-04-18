import httpx
import logging
import server.constants
import server.exceptions
from typing import Any


class WikiContentGetter:

    PARAMS = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "pageids": "",      # ← pass the pageid directly from your search result
        "explaintext": 1    # ← strips wiki markup, returns clean plain text
    }

    def __init__(self, wiki_data: dict[str, Any]) -> None:
        """
         Expected shape of data passed to WikiContentGetter is

         {
            'title': 'Rodtang Jitmuangnon',
            'page_id': 60654920
         }
        """
        self.logger = logging.getLogger(__name__)

        if not wiki_data:
            msg = "Empty wiki_data passed to WikiContentGetter"
            self.logger.warning(msg)
            raise server.exceptions.FetchError(msg)

        self.wiki_data = wiki_data

    async def get_wiki_content(self) -> dict[str, Any]:

        pageid = self.wiki_data.get("page_id", "")

        if not pageid:
            msg = "Failed to extract pageid from wiki_data"
            self.logger.warning(msg)
            raise server.exceptions.FetchError(msg)

        params = {**self.PARAMS, "pageids": pageid}

        try:
            async with httpx.AsyncClient(headers=server.constants.WIKIPEDIA_HEADERS) as client:
                response = await client.get(server.constants.WIKIPEDIA_URL, params=params)
        except httpx.RequestError as e:
            self._handle_fetch_exception(f"Network error reaching Wikipedia: {e}")

        if response.status_code != 200:
            title = self.wiki_data.get("title", "unknown")
            self._handle_fetch_exception(f"Wikipedia returned {response.status_code} for {title}")

        results = response.json()

        if not results:
            self._handle_fetch_exception(f"No Wikipedia article found for page_id '{pageid}'")

        pages = results.get("query", {}).get("pages", {})
        page = pages.get(str(pageid), {})
        extract = page.get("extract", "")

        if not extract:
            self._handle_fetch_exception(f"No content found for page_id '{pageid}'")

        return {
            **self.wiki_data,
            "content": extract
        }

    def _handle_fetch_exception(self, msg: str) -> None:
        self.logger.warning(msg)
        raise server.exceptions.FetchError(msg)
