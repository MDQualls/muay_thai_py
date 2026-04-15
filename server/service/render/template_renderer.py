import logging
from jinja2 import Environment, FileSystemLoader
from typing import Any
from server.exceptions import RenderError

class TemplateRenderer:

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def render_template(
            self,
            enriched_data: dict[str, Any],
            template_name: str,
            slide_num: int) -> str:
        
        try: 
            env = Environment(loader=FileSystemLoader("templates"))
            template = env.get_template(template_name)

            return template.render(fighter=enriched_data, slide_num=slide_num, total_slides=3)
        except Exception as e:
            self.logger.error("Failed to render template for '%s': %s", enriched_data.get("name"), e)
            raise RenderError(f"Template rendering failed: {e}") from e
        