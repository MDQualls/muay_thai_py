import asyncio
from server.renderer import render_carousel
from server.enricher import enrich_fighter
from server.fetcher import get_fighter_data
from server.uploader import upload_carousel
from server.publisher import post_carousel
from server.caption_builder import build_caption

async def main() -> None:
    raw_data = await get_fighter_data("jonathan haggerty")
    enriched_data = await enrich_fighter(raw_data)

    paths = await render_carousel(enriched_data)
    for path in paths:
        print(f"Slide saved to: {path}")

    uploaded_paths = await upload_carousel(paths)
    for upload in uploaded_paths:
        print(f"Slide {upload} uploaded to R2")

    caption = build_caption(enriched_data)

    print(f"Caption:\n{caption}\n")
    
    post_id = await post_carousel(uploaded_paths, caption)
    print(f"Instragram post completed with post_id {post_id}")


asyncio.run(main())