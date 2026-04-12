import logging
from typing import Any

logger = logging.getLogger(__name__)


async def render_card(enriched_data: dict[str, Any]) -> str:
    """Render the fighter card HTML template and screenshot it to PNG via Playwright.

    Args:
        enriched_data: dict returned from enricher.enrich_fighter()

    Returns:
        str path to the generated PNG e.g. "output/rodtang_20240101_120000.png"

    TODO:
    - Create a Jinja2 Environment pointed at the templates/ directory
    - Load templates/card.html and render it with enriched_data
    - Write the rendered HTML to a temp file (or use a data: URI)
    - Use make_output_path() from this module to generate the output filename
    - Launch Playwright async API: async with async_playwright() as p
    - Launch Chromium headless, open a new page
    - Set viewport to 1080x1080
    - Navigate to the rendered HTML file (use file:// URI)
    - page.screenshot(path=output_path, full_page=False)
    - Close browser
    - Return the output path as a string
    - Raise RenderError on any Playwright or template failure
    """
    logger.info("Rendering card for fighter: %s", enriched_data.get("name"))

    # TODO: implement Playwright rendering
    return "output/card.png"


def make_output_path(fighter_name: str) -> str:
    """Generate a timestamped output path for a fighter card PNG.

    Args:
        fighter_name: Fighter's full name e.g. "Rodtang Jitmuangnon"

    Returns:
        str path e.g. "output/rodtang_jitmuangnon_20240101_120000.png"
    """
    from datetime import datetime
    from pathlib import Path

    slug = fighter_name.lower().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(Path("output") / f"{slug}_{timestamp}.png")
