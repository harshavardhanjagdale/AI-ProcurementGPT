"""
Multi-provider LLM client with runtime switching.
Supports Anthropic, OpenAI, and Google Gemini.
All consumers use the same generate()/generate_json() interface.
"""
import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

JSON_MODE_INSTRUCTION = (
    "\n\nRespond with ONLY a single valid JSON object. "
    "No markdown code fences, no explanation, no text before or after the JSON."
)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2

_TRANSIENT_ERRORS = (
    asyncio.CancelledError,
    ConnectionError,
    TimeoutError,
    OSError,
)

AVAILABLE_MODELS = {
    "anthropic": [
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
        {"id": "claude-haiku-4-20250414", "name": "Claude Haiku 4"},
        {"id": "claude-opus-4-20250514", "name": "Claude Opus 4"},
    ],
    "openai": [
        {"id": "gpt-4o", "name": "GPT-4o"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
        {"id": "o3-mini", "name": "O3 Mini"},
    ],
    "gemini": [
        {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro"},
        {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
    ],
}


def _strip_json_fences(content: str) -> str:
    """Strip markdown code fences if the model wrapped its JSON output in them."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.endswith("```"):
            text = text[:-3]
        elif "```" in text:
            text = text.rsplit("```", 1)[0]
    return text.strip()


# ---------------------------------------------------------------------------
# Abstract Base Provider
# ---------------------------------------------------------------------------

class BaseLLMProvider(ABC):
    """Abstract base for all LLM providers."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    async def _call(self, system: str, user_prompt: str, max_tokens: int) -> str:
        """Provider-specific API call. Must return raw text."""
        ...

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> str:
        """Generate text with automatic retry on transient failures."""
        system = system_prompt + JSON_MODE_INSTRUCTION if json_mode else system_prompt

        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return await self._call(system, user_prompt, max_tokens)
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

        logger.error(f"LLM generation failed after {MAX_RETRIES} attempts: {last_exc}")
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


# ---------------------------------------------------------------------------
# Anthropic Provider
# ---------------------------------------------------------------------------

class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=api_key, timeout=120.0)

    async def _call(self, system: str, user_prompt: str, max_tokens: int) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


# ---------------------------------------------------------------------------
# OpenAI Provider
# ---------------------------------------------------------------------------

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key, timeout=120.0)

    async def _call(self, system: str, user_prompt: str, max_tokens: int) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Gemini Provider
# ---------------------------------------------------------------------------

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        from google import genai
        self.client = genai.Client(api_key=api_key)

    async def _call(self, system: str, user_prompt: str, max_tokens: int) -> str:
        from google.genai import types

        full_prompt = f"{system}\n\n{user_prompt}"
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model,
            contents=full_prompt,
            config=types.GenerateContentConfig(max_output_tokens=max_tokens),
        )
        return response.text or ""


# ---------------------------------------------------------------------------
# LLM Client Manager (singleton)
# ---------------------------------------------------------------------------

PROVIDER_MAP = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}


class LLMClientManager:
    """
    Manages the active LLM provider. Can switch providers at runtime.
    Exposes generate() and generate_json() that delegate to the active provider.
    """

    def __init__(self):
        self._provider: Optional[BaseLLMProvider] = None
        self._provider_name: str = ""
        self._model: str = ""
        self._initialize_from_env()

    def _initialize_from_env(self):
        """Initialize from .env configuration as fallback."""
        provider_name = getattr(settings, "LLM_PROVIDER", "anthropic")
        api_key = ""
        model = ""

        if provider_name == "anthropic":
            api_key = settings.ANTHROPIC_API_KEY
            model = settings.ANTHROPIC_MODEL
        elif provider_name == "openai":
            api_key = getattr(settings, "OPENAI_API_KEY", "")
            model = getattr(settings, "OPENAI_MODEL", "gpt-4o")
        elif provider_name == "gemini":
            api_key = getattr(settings, "GOOGLE_API_KEY", "")
            model = getattr(settings, "GOOGLE_MODEL", "gemini-2.5-flash")

        if api_key:
            self.set_provider(provider_name, api_key, model)
        else:
            logger.warning("No LLM API key configured. LLM calls will fail until a provider is set.")

    def set_provider(self, provider_name: str, api_key: str, model: str):
        """Switch to a different provider at runtime."""
        provider_name = provider_name.lower()
        if provider_name not in PROVIDER_MAP:
            raise ValueError(f"Unknown provider: {provider_name}. Must be one of: {list(PROVIDER_MAP.keys())}")

        provider_class = PROVIDER_MAP[provider_name]
        self._provider = provider_class(api_key=api_key, model=model)
        self._provider_name = provider_name
        self._model = model
        logger.info(f"LLM provider switched to: {provider_name} (model: {model})")

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model(self) -> str:
        return self._model

    @property
    def is_configured(self) -> bool:
        return self._provider is not None

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> str:
        if not self._provider:
            raise RuntimeError("No LLM provider configured. Go to Settings to configure one.")
        return await self._provider.generate(system_prompt, user_prompt, max_tokens, json_mode)

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 3000,
    ) -> dict | None:
        if not self._provider:
            raise RuntimeError("No LLM provider configured. Go to Settings to configure one.")
        return await self._provider.generate_json(system_prompt, user_prompt, max_tokens)

    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 1500,
    ) -> str:
        """Multi-turn chat (extracts system message and delegates to generate)."""
        if not self._provider:
            raise RuntimeError("No LLM provider configured. Go to Settings to configure one.")

        system_prompt = ""
        user_content_parts = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                user_content_parts.append(f"{msg['role']}: {msg['content']}")

        user_prompt = "\n".join(user_content_parts)
        return await self._provider.generate(system_prompt, user_prompt, max_tokens)


# Module-level singleton - all consumers import this
llm_client = LLMClientManager()
