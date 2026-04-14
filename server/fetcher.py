import logging
from typing import Any
from server.service.wiki.wiki_searcher import WikiSearcher
from server.service.wiki.wiki_content_getter import WikiContentGetter

logger = logging.getLogger(__name__)


async def get_fighter_data(fighter_name: str) -> dict[str, Any]:
    """Fetch fighter data from the Wikipedia API.

    Args:
        fighter_name: Fighter's full name e.g. "Rodtang Jitmuangnon"
    """

    logger.info("Fetching fighter data for: %s", fighter_name)

    # search wikipedia for an article about the figher
    searcher = WikiSearcher(fighter_name)
    search_result = await searcher.do_wiki_search()

    # get the contents of the wikipedia article
    getter = WikiContentGetter(search_result)
    content = await getter.get_wiki_content()

    return {
        "name": fighter_name,
        "wikipedia_title": content["title"],
        "wikipedia_url": f"https://en.wikipedia.org/wiki/{content['title'].replace(' ', '_')}",
        "wikipedia_extract": content["content"],
    }
