import asyncio
from server.renderer import render_carousel
from server.enricher import enrich_fighter
from server.fetcher import get_fighter_data
from server.uploader import upload_carousel

async def main() -> None:
    raw_data = await get_fighter_data("Rodtang")
    enriched_data = await enrich_fighter(raw_data)

    paths = await render_carousel(enriched_data)
    for path in paths:
        print(f"Slide saved to: {path}")

    uploaded_paths = await upload_carousel(paths)
    for upload in uploaded_paths:
        print(f"Slide {upload} uploaded to R2")


asyncio.run(main())