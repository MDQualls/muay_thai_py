import asyncio
from server.renderer import render_carousel
from server.enricher import enrich_fighter
from server.fetcher import get_fighter_data


enriched_data = {
    "name": "Rodtang Jitmuangnon",
    "nickname": None,
    "nationality": "Thai",
    "gym": "Jitmuangnon Gym",
    "record_wins": None,
    "record_losses": None,
    "record_kos": None,
    "fighting_style": "Aggressive pressure fighter with devastating clinch work and elite cardio",
    "signature_weapons": [
        "Liver shot",
        "Elbow strikes",
        "Knee strikes from clinch",
        "Clinch dominance",
    ],
    "attributes": {
        "aggression": 9,
        "power": 8,
        "footwork": 8,
        "clinch": 9,
        "cardio": 9,
        "technique": 8,
    },
    "bio": (
        "Rodtang Jitmuangnon is one of the most accomplished and highest-paid Muay Thai fighters "
        "in the world. Starting his professional career at just eight years old to support his "
        "family, he moved to Bangkok at fourteen to join Jitmuangnon gym. He captured the ONE "
        "Flyweight Muay Thai World Championship in 2019 and became the longest-reigning champion "
        "in the division with five successful title defenses. Known for his relentless aggression, "
        "elite cardio, and devastating liver shots, Rodtang holds the record for most decision "
        "wins in ONE Championship history."
    ),
    "fun_fact": (
        "Rodtang began training Muay Thai at age seven and competed professionally at eight "
        "to help his family financially."
    ),
    "wikipedia_url": "https://en.wikipedia.org/wiki/Rodtang_Jitmuangnon",
}


async def main() -> None:
    raw_data = await get_fighter_data("Rodtang")
    enriched_data = await enrich_fighter(raw_data)
    paths = await render_carousel(enriched_data)
    for path in paths:
        print(f"Slide saved to: {path}")


asyncio.run(main())

