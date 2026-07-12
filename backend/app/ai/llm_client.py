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
from app.ai.token_tracker import record_usage

logger = logging.getLogger(__name__)

# Prompt caching: min cacheable prefix is ~1024 tokens (Haiku) / ~2048 tokens
# (Sonnet/Opus). Below this the API silently ignores cache_control, so we only
# tag the system block when it's plausibly long enough to matter. Verify it
# actually engaged via usage.cache_read_input_tokens (surfaced in token_tracker).
_MIN_CHARS_TO_CACHE = 8000  # ~2k+ tokens; at/above Sonnet's cacheable-prefix floor

JSON_MODE_INSTRUCTION = (
    "\n\nRespond with ONLY a single valid JSON object. "
    "No markdown code fences, no explanation, no text before or after the JSON."
)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2

# Transient network/IO failures worth retrying. NOTE: asyncio.CancelledError is
# deliberately NOT here — cancellation must propagate so background tasks (the
# streaming workflow runs as fire-and-forget tasks) can shut down promptly.
# The provider SDKs (Anthropic/OpenAI) also retry 429/5xx/connection errors
# internally, so this outer loop is a second, provider-agnostic safety net.
_TRANSIENT_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

AVAILABLE_MODELS = {
    # Current Anthropic model IDs (use the bare alias — do NOT append date suffixes).
    # Opus 4.8 is the most capable; Sonnet 5 is the balanced default; Haiku 4.5 is fast/cheap.
    "anthropic": [
        {"id": "claude-opus-4-8", "name": "Claude Opus 4.8"},
        {"id": "claude-sonnet-5", "name": "Claude Sonnet 5"},
        {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5"},
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


def _maybe_wrap_client(client, provider: str):
    """
    Wrap a provider SDK client with LangSmith's tracing wrapper so each individual
    API call shows up in LangSmith as a nested LLM span *with token counts, cost and
    latency* under its LangGraph node. Without this, LangSmith sees the graph nodes
    but has no token data (the nodes call the raw SDK), which is exactly why the
    "Cost and Tokens" column stays empty.

    No-op (returns the client unchanged) if tracing is off or langsmith isn't
    available -- so nothing breaks when running without LangSmith.
    """
    logger.warning(
        f"DEBUG: _maybe_wrap_client(provider={provider}, tracing={getattr(settings, 'LANGSMITH_TRACING', False)})"
    )
    if not getattr(settings, "LANGSMITH_TRACING", False):
        return client
    try:
        from langsmith import wrappers
        wrap_fn = {
            "anthropic": getattr(wrappers, "wrap_anthropic", None),
            "openai": getattr(wrappers, "wrap_openai", None),
            "gemini": getattr(wrappers, "wrap_gemini", None),
        }.get(provider)
        if wrap_fn is None:
            return client
        wrapped = wrap_fn(client)
        logger.info(f"LangSmith tracing wrapper attached to {provider} client")
        return wrapped
    except Exception as e:
        logger.warning(f"Could not attach LangSmith wrapper to {provider} client: {e}")
        return client


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
            except asyncio.CancelledError:
                # Never retry a cancellation — let it propagate to unwind the task.
                raise
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
        self.client = _maybe_wrap_client(AsyncAnthropic(api_key=api_key, timeout=120.0), "anthropic")

    def _build_system_param(self, system: str):
        """
        Return the `system` argument for the Anthropic API. When prompt caching is
        enabled and the system prompt is large enough to be cacheable, send it as a
        content block with cache_control=ephemeral so repeated calls with the same
        system prompt read it from cache (~90% cheaper, lower latency) instead of
        re-processing it every time. The system prompts here (parse/extract/analyze)
        are static per node, which is exactly the shape prompt caching rewards.
        """
        if settings.ANTHROPIC_PROMPT_CACHING and len(system) >= _MIN_CHARS_TO_CACHE:
            return [{
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }]
        return system

    async def _call(self, system: str, user_prompt: str, max_tokens: int) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self._build_system_param(system),
            messages=[{"role": "user", "content": user_prompt}],
        )

        usage = getattr(response, "usage", None)
        if usage is not None:
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
            input_tok = getattr(usage, "input_tokens", 0)
            output_tok = getattr(usage, "output_tokens", 0)

            if cache_read or cache_write:
                total_input = input_tok + cache_read
                pct = (cache_read / total_input * 100) if total_input > 0 else 0
                logger.info(
                    f"[PROMPT-CACHE] input={input_tok} cache_read={cache_read} "
                    f"cache_write={cache_write} output={output_tok} "
                    f"| {'HIT' if cache_read else 'WRITE'} ({pct:.0f}% cached)"
                )

            record_usage(
                provider="anthropic",
                model=self.model,
                input_tokens=input_tok,
                output_tokens=output_tok,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
                label=f"stop={getattr(response, 'stop_reason', '?')}",
            )

        # Surface truncation instead of silently returning a half-formed answer that
        # downstream JSON parsing would choke on. request id makes Anthropic support
        # tickets traceable.
        if getattr(response, "stop_reason", None) == "max_tokens":
            logger.warning(
                "Anthropic response truncated at max_tokens=%d (request_id=%s). "
                "Consider raising max_tokens for this call.",
                max_tokens, getattr(response, "_request_id", None),
            )

        return "".join(block.text for block in response.content if block.type == "text")


# ---------------------------------------------------------------------------
# OpenAI Provider
# ---------------------------------------------------------------------------

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        from openai import AsyncOpenAI
        self.client = _maybe_wrap_client(AsyncOpenAI(api_key=api_key, timeout=120.0), "openai")

    async def _call(self, system: str, user_prompt: str, max_tokens: int) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )

        usage = getattr(response, "usage", None)
        if usage is not None:
            details = getattr(usage, "prompt_tokens_details", None)
            cached = getattr(details, "cached_tokens", 0) if details else 0
            record_usage(
                provider="openai",
                model=self.model,
                # OpenAI's prompt_tokens already includes cached tokens; split them
                # out so the cache line reads consistently across providers.
                input_tokens=(getattr(usage, "prompt_tokens", 0) or 0) - (cached or 0),
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                cache_read_tokens=cached or 0,
            )

        return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Gemini Provider
# ---------------------------------------------------------------------------

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        from google import genai
        self.client = _maybe_wrap_client(genai.Client(api_key=api_key), "gemini")

    async def _call(self, system: str, user_prompt: str, max_tokens: int) -> str:
        from google.genai import types

        full_prompt = f"{system}\n\n{user_prompt}"
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model,
            contents=full_prompt,
            config=types.GenerateContentConfig(max_output_tokens=max_tokens),
        )

        meta = getattr(response, "usage_metadata", None)
        if meta is not None:
            cached = getattr(meta, "cached_content_token_count", 0) or 0
            record_usage(
                provider="gemini",
                model=self.model,
                input_tokens=(getattr(meta, "prompt_token_count", 0) or 0) - cached,
                output_tokens=getattr(meta, "candidates_token_count", 0) or 0,
                cache_read_tokens=cached,
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
