from typing import Protocol

from app.agent.intents import ParsedIntent
from app.schemas.reviews import ReviewParsedUpdate


class LLMProvider(Protocol):
    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        ...

    async def parse_review(self, *, text: str) -> ReviewParsedUpdate:
        ...

    async def reminder_copy(self, *, title: str, kind: str, context: str | None = None) -> str:
        ...

