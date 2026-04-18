import anthropic
import logging
from server.config import settings
from server.exceptions import EnrichmentError
from server.service.enrich.prompter import Prompter


class EnrichmentHandler:

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.prompter = Prompter()
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def enrich(self, extract: str) -> anthropic.types.Message:
        prompt = self.prompter.build_prompt(extract)

        if not prompt:
            msg = "Failed to build prompt for enricher"
            self.logger.warning(msg)
            raise EnrichmentError(msg)

        message = await self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message
