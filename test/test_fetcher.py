import httpx
import asyncio

from server.wiki_searcher import WikiSearcher

searcher = WikiSearcher("Rodtang")
r = asyncio.run(searcher.do_wiki_search())

print(r)
