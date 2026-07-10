"""
Per-run LLM token-usage tracking.

Every LLM call in this app goes through `app/ai/llm_client.py`. Each provider
reports the token usage it got back from the API into the *currently active*
accumulator via `record_usage()`. A workflow run activates an accumulator with
`track_usage(run_id)` (see `session_workflow.py`), so all the LLM calls made by
the LangGraph nodes during that run are attributed to that run.

Why a ContextVar instead of threading a counter through every node/state field:
the token count is a pure cross-cutting observability concern. Nodes shouldn't
have to know or care about it, and `ProcurementState` shouldn't grow a field for
it. A ContextVar gives us "ambient" attribution that works across `await`
boundaries without touching a single call site.

The numbers are normalized across providers into one shape so the demo/UI can
show a single "tokens + cost" line regardless of whether Anthropic, OpenAI, or
Gemini answered:
    input_tokens, output_tokens, cache_read_tokens, cache_write_tokens
"""
from __future__ import annotations

import contextvars
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Indicative USD per 1M tokens. Not billing-grade — enough to put a real cost
# figure on the demo dashboard. Keyed by a loose model-family match.
_PRICING_PER_MTOK = {
    # (input, output, cache_read, cache_write)
    "claude-opus": (15.0, 75.0, 1.5, 18.75),
    "claude-sonnet": (3.0, 15.0, 0.30, 3.75),
    "claude-haiku": (0.80, 4.0, 0.08, 1.0),
    "gpt-4o-mini": (0.15, 0.60, 0.075, 0.0),
    "gpt-4o": (2.5, 10.0, 1.25, 0.0),
    "gemini-2.5-pro": (1.25, 10.0, 0.31, 0.0),
    "gemini-2.5-flash": (0.30, 2.5, 0.075, 0.0),
    "gemini": (0.30, 2.5, 0.075, 0.0),
}


def _price_for(model: str) -> tuple[float, float, float, float]:
    m = (model or "").lower()
    for key, price in _PRICING_PER_MTOK.items():
        if key in m:
            return price
    return (0.0, 0.0, 0.0, 0.0)


@dataclass
class CallRecord:
    provider: str
    model: str
    label: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int

    @property
    def cost_usd(self) -> float:
        pi, po, pcr, pcw = _price_for(self.model)
        return (
            self.input_tokens * pi
            + self.output_tokens * po
            + self.cache_read_tokens * pcr
            + self.cache_write_tokens * pcw
        ) / 1_000_000


@dataclass
class UsageAccumulator:
    run_id: str
    calls: list[CallRecord] = field(default_factory=list)

    def record(self, rec: CallRecord) -> None:
        self.calls.append(rec)

    @property
    def total_calls(self) -> int:
        return len(self.calls)

    @property
    def input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def cache_read_tokens(self) -> int:
        return sum(c.cache_read_tokens for c in self.calls)

    @property
    def cache_write_tokens(self) -> int:
        return sum(c.cache_write_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of input tokens that were served from cache (cost ~90% less)."""
        billed_input = self.input_tokens + self.cache_read_tokens
        if billed_input == 0:
            return 0.0
        return self.cache_read_tokens / billed_input

    def summary(self) -> dict:
        return {
            "calls": self.total_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_tokens": self.total_tokens,
            "cache_hit_rate": round(self.cache_hit_rate, 3),
            "cost_usd": round(self.cost_usd, 6),
        }


# The ambient accumulator for the current async context. None = not inside a
# tracked run (calls are still made, they're just not attributed anywhere).
_current: contextvars.ContextVar[UsageAccumulator | None] = contextvars.ContextVar(
    "llm_usage_accumulator", default=None
)


def get_current_usage() -> UsageAccumulator | None:
    return _current.get()


def record_usage(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    label: str = "",
) -> None:
    """Called by each provider after an API response. No-op if not in a tracked run."""
    rec = CallRecord(
        provider=provider,
        model=model,
        label=label,
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        cache_read_tokens=int(cache_read_tokens or 0),
        cache_write_tokens=int(cache_write_tokens or 0),
    )
    # Always log the individual call — useful even outside a tracked run.
    logger.info(
        "[LLM-USAGE] %s/%s in=%d out=%d cache_read=%d cache_write=%d ~$%.5f %s",
        rec.provider, rec.model, rec.input_tokens, rec.output_tokens,
        rec.cache_read_tokens, rec.cache_write_tokens, rec.cost_usd, rec.label,
    )
    acc = _current.get()
    if acc is not None:
        acc.record(rec)


@contextmanager
def track_usage(run_id: str):
    """Activate a fresh accumulator for the duration of a workflow run.

    Usage:
        with track_usage(thread_id) as usage:
            ... run the graph ...
        logger.info(usage.summary())
    """
    acc = UsageAccumulator(run_id=run_id)
    token = _current.set(acc)
    try:
        yield acc
    finally:
        _current.reset(token)
