"""
Claude (Anthropic) LLM client wrapper for all AI operations.
Provides structured generation, chat completion, and JSON mode.
"""
import asyncio
import json
import logging

from anthropic import AsyncAnthropic

from app.core.config import settings

logger = logging.getLogger(__name__)

JSON_MODE_INSTRUCTION = (
    "\n\nRespond with ONLY a single valid JSON object. "
    "No markdown code fences, no explanation, no text before or after the JSON."
)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds

_TRANSIENT_ERRORS = (
    asyncio.CancelledError,
    ConnectionError,
    TimeoutError,
    OSError,
)


class LLMClient:
    def __init__(self):
        self.client = AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=120.0,
        )
        self.model = settings.ANTHROPIC_MODEL

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> str:
        """Basic chat completion with automatic retry on transient failures."""
        system = system_prompt + JSON_MODE_INSTRUCTION if json_mode else system_prompt

        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return _extract_text(response)
            except _TRANSIENT_ERRORS as e:
                last_exc = e
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    f"LLM call attempt {attempt}/{MAX_RETRIES} failed "
                    f"({type(e).__name__}), retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"LLM generation failed (non-retryable): {e}")
                raise

        logger.error(
            f"LLM generation failed after {MAX_RETRIES} attempts: {last_exc}"
        )
        raise last_exc  # type: ignore[misc]

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 3000,
    ) -> dict | None:
        """Generate structured JSON response."""
        try:
            content = await self.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                json_mode=True,
            )
            return json.loads(_strip_json_fences(content))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON: {e}")
            return None

    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 1500,
    ) -> str:
        """Multi-turn chat completion. A leading {"role": "system", ...} message, if present, is pulled out."""
        system_prompt = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                chat_messages.append(msg)

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": chat_messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self.client.messages.create(**kwargs)
                return _extract_text(response)
            except _TRANSIENT_ERRORS as e:
                last_exc = e
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    f"LLM chat attempt {attempt}/{MAX_RETRIES} failed "
                    f"({type(e).__name__}), retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"LLM chat failed (non-retryable): {e}")
                raise

        logger.error(
            f"LLM chat failed after {MAX_RETRIES} attempts: {last_exc}"
        )
        raise last_exc  # type: ignore[misc]


def _extract_text(response) -> str:
    return "".join(block.text for block in response.content if block.type == "text")


def _strip_json_fences(content: str) -> str:
    """Strip markdown code fences (```json ... ```) if the model wrapped its JSON output in them."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.endswith("```"):
            text = text[:-3]
        elif "```" in text:
            text = text.rsplit("```", 1)[0]
    return text.strip()


llm_client = LLMClient()
