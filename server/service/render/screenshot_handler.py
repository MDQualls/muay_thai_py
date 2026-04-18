import logging
from pathlib import Path
from playwright.async_api import async_playwright, Error as PlaywrightError
from server.exceptions import RenderError


class ScreenshotHandler:

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    async def create_jpeg(
            self,
            fighter_name: str,
            html: str,
            output_path: Path) -> None:

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.set_viewport_size({"width": 1080, "height": 1080})
                await page.set_content(html, wait_until="networkidle")
                await page.screenshot(path=str(output_path), full_page=False, type="jpeg", quality=95)
                await browser.close()
        except PlaywrightError as e:
            self.logger.error("Failed to generate screenshot jpeg for '%s': %s", fighter_name, e)
            raise RenderError(f"Screenshot jpeg generation failed: {e}") from e
