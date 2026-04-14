import logging
from typing import Any
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright

from server.exceptions import RenderError

logger = logging.getLogger(__name__)


async def render_carousel(enriched_data: dict[str, Any]) -> list[Path]:
    """Render all three carousel slides and return their paths.

    Args:
        enriched_data: dict returned from enricher.enrich_fighter()

    Returns:
        list of 3 Paths in order: [impact_path, stats_path, story_path]
    """    
    paths = []
    for slide_num, template_name in enumerate(["slide_1_impact.html", "slide_2_stats.html", "slide_3_story.html"], 1):
        path = await render_slide(enriched_data, template_name, slide_num)
        paths.append(path)
    return paths


async def render_slide(
    enriched_data: dict[str, Any],
    template_name: str,
    slide_num: int,
) -> Path:
    """Render a single carousel slide to JPEG.

    Args:
        enriched_data: dict returned from enricher.enrich_fighter()
        template_name: filename of the template e.g. "slide_1_impact.html"
        slide_num: 1, 2, or 3 — used in the output filename

    Returns:
        Path to the generated JPEG
    """
    try:
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template(template_name)

        html = template.render(fighter=enriched_data, slide_num=slide_num, total_slides=3)

        output_path = make_output_path(enriched_data.get("name"), slide_num)

        async with async_playwright( ) as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1080, "height": 1080})
            await page.set_content(html, wait_until="networkidle")
            await page.screenshot(path=str(output_path), full_page=False, type="jpeg", quality=95)
            await browser.close()

        return output_path

    except Exception as e:
        logger.error("Failed to render card for '%s': %s", enriched_data.get("name"), e)
        raise RenderError(f"Card rendering failed: {e}") from e


def make_output_path(fighter_name: str, slide_num: int) -> Path:
    """Generate a timestamped output path for a carousel slide JPEG.

    Args:
        fighter_name: Fighter's full name e.g. "Rodtang Jitmuangnon"
        slide_num: Slide number 1, 2, or 3

    Returns:
        Path e.g. "output/rodtang_jitmuangnon_20240101_120000_slide1.jpg"
    """
    slug = fighter_name.lower().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("output") / f"{slug}_{timestamp}_slide{slide_num}.jpg"
