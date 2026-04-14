import asyncio
import server.enricher
from server.fetcher import get_fighter_data

async def main():
    raw_data = await get_fighter_data("Petchtanong Petchfergus")
    result = await server.enricher.enrich_fighter(raw_data)
    print(result)

asyncio.run(main())