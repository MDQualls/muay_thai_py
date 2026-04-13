import httpx
import asyncio

from server.fetcher import get_fighter_data

r = asyncio.run(get_fighter_data("Rodtang Jitmuangnon"))

print(r)
