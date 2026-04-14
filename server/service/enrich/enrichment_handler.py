import anthropic
import logging
from server.config import settings
from typing import Any
from server.service.enrich.prompter import Prompter

client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

class EnrichmentHandler:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.prompter = Prompter()

    async def enrich(self, extract: dict) -> anthropic.types.Message:
        
        prompt = self.prompter.build_prompt(extract)

        if not prompt:
            msg = "Failed to build prompt for enricher"
            self.logger.warning(msg)
            raise ValueError(msg)

        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message