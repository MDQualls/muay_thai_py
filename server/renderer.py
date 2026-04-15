import logging
from typing import Any
from pathlib import Path
from server.service.render.template_renderer import TemplateRenderer
from server.service.render.screenshot_handler import ScreenshotHandler
from server.service.path_handler import PathHandler
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
        renderer = TemplateRenderer()
        html = renderer.render_template(enriched_data,template_name,slide_num)

        output_path = PathHandler.make_output_path(enriched_data.get("name"), slide_num)

        screenshot_handler = ScreenshotHandler()
        await screenshot_handler.create_jpeg(enriched_data.get("name"), html, output_path)

        return output_path

    except Exception as e:
        logger.error("Failed to render card: %s", e)
        raise RenderError(f"Card rendering failed: {e}") from e
