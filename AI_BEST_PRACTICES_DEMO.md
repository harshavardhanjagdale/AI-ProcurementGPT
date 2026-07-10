# ProcureGPT — Agentic Design & AI Best Practices (Demo Walkthrough)

> **Audience:** tech lead / reviewers.
> **Goal:** show *how* this is a real agentic system and *which* production AI
> best practices it applies — with working code, not slideware. Every claim
> below points at a file you can open, and the observability/eval pieces run live.
>
> Companion docs: [`TECHNICAL_ARCHITECTURE.md`](TECHNICAL_ARCHITECTURE.md) (deep
> technical reference) · [`CLAUDE.md`](CLAUDE.md) (project brief) ·
> `CLAUDE.local.md` (local demo runbook).

---

## 0. The 30-second pitch

A user types *"buy 10 Dell laptops for the sales team"* in plain English.
An **agent graph** parses it, **semantically matches** suppliers, drafts and
emails RFQs, **pauses** for supplier replies, **OCRs** the quote PDFs into
structured data, ranks them, **pauses again** for a human approve/negotiate/cancel
decision, then generates and emails a purchase-order PDF — all while **tracking
tokens and cost per run**, **caching prompts**, and **evaluating prompt quality**
in CI.

The engineering around it (guardrail **hooks**, reusable **skills**, layered
docs) applies the same "agentic" discipline to *how we build the app*.

---

## 1. What makes this *agentic* (not just "an app that calls an LLM")

The core is a **LangGraph state machine** — a directed graph of "agent" nodes
sharing one typed state object. This is the single most important thing to
convey: it's an **orchestrated multi-step agent**, with real control flow,
human-in-the-loop pauses, and durable state.

| Agentic property | How it shows up here | Where |
|---|---|---|
| **Graph of specialized agents** | 12 nodes (Parser, Vendor, Email, OCR, Negotiation, PO…), each a function that reads shared `ProcurementState` and returns a partial update | [`backend/app/agents/orchestrator.py`](backend/app/agents/orchestrator.py), [`nodes/`](backend/app/agents/nodes/) |
| **Conditional routing** | `route_after_validation`, `route_user_decision`, `route_negotiation_result` branch the flow (multi-vendor vs direct-buy; approve vs negotiate vs cancel) | `orchestrator.py` conditional edges |
| **Human-in-the-loop** | Compiled with `interrupt_before=["user_decision_gate"]` and `interrupt_after=["await_supplier_replies"]` — the graph *literally stops* and returns control | `orchestrator.py::init_procurement_graph` |
| **Durable state (survives restart)** | `AsyncSqliteSaver` checkpointer — a workflow can sit paused for *days* waiting on a supplier email and resume after a redeploy | `orchestrator.py` |
| **Event-driven resume** | An inbound email (IMAP poll / webhook / manual) re-invokes the paused graph by its `thread_id` | [`backend/app/email/background_worker.py`](backend/app/email/background_worker.py), [`api/v1/webhooks.py`](backend/app/api/v1/webhooks.py) |
| **Streaming observability** | `graph.astream(stream_mode="updates")` commits each node's progress to the DB as it lands, so the UI lights up node-by-node | [`backend/app/workflows/session_workflow.py`](backend/app/workflows/session_workflow.py) |

**Honest framing (say this — it signals maturity):** this is a *code-orchestrated
workflow*, not an open-ended tool-calling agent. The steps are fixed and
deterministic, so a LangGraph state machine is the correct tier — we get
agent-like autonomy and human-in-the-loop control *without* the unpredictability
of a model deciding its own control flow. We reserve model-driven tool use for
genuinely open-ended sub-tasks (we don't have any yet).

---

## 2. RAG & vector embeddings — semantic vendor matching

Supplier selection is **retrieval-augmented**, not keyword `LIKE` matching.

- **Embeddings:** `sentence-transformers` **`all-MiniLM-L6-v2`** (384-dim), with
  `normalize_embeddings=True`. → [`backend/app/ai/embeddings.py`](backend/app/ai/embeddings.py)
- **Vector store:** supplier embeddings are **precomputed** and stored as a
  `BLOB` on each `suppliers` row (batch job:
  [`scripts/generate_embeddings.py`](backend/scripts/generate_embeddings.py));
  generated on-the-fly if missing.
- **Retrieval:** the RFQ text (`title + description + categories`) is embedded and
  ranked against all candidate suppliers by **cosine similarity**; top-K (default
  5) are linked to the RFQ. → [`backend/app/ai/vector_search.py`](backend/app/ai/vector_search.py)
- **Hybrid filter:** a DB category pre-filter narrows candidates first, then
  vector ranking orders them — classic hybrid retrieval.

> **The RAG story in one line:** we *retrieve* the most semantically relevant
> suppliers via vector similarity and *augment* the downstream RFQ-generation
> step with them — retrieval feeding generation.

**OCR is a second "structured extraction" RAG-adjacent pipeline:** supplier quote
PDFs → images (pdf2image @300dpi) → text (Tesseract) → **LLM turns messy OCR text
into validated quotation JSON**. → [`backend/app/ocr/pipeline.py`](backend/app/ocr/pipeline.py)

---

## 3. Token & cost observability (implemented)

**Problem it solves:** "how much does one procurement cost in LLM spend, and
where?" Previously invisible. Now every call is attributed to its run.

- **Provider-agnostic tracker** with a `ContextVar` accumulator — no node has to
  know about it; attribution works across `await` boundaries.
  → [`backend/app/ai/token_tracker.py`](backend/app/ai/token_tracker.py)
- **Captured at the provider boundary** for **all three** providers (Anthropic
  `usage`, OpenAI `usage`, Gemini `usage_metadata`), normalized to one shape:
  `input / output / cache_read / cache_write`. → [`backend/app/ai/llm_client.py`](backend/app/ai/llm_client.py)
- **Per-run attribution:** `session_workflow.py` wraps the graph stream in
  `track_usage(thread_id)`, so every LLM call the nodes make rolls up to that
  procurement.
- **Surfaced three ways:**
  - per call → `[LLM-USAGE] anthropic/claude-sonnet-5 in=… out=… ~$…` in the log
  - running total per node → `[NODE-DONE] … | tokens so far: … (~$…)`
  - final roll-up → `[TOKEN-USAGE] {…summary…}` and attached to each
    `workflow_events.metadata_json.tokens` so the timeline UI can show live spend.
- **Indicative cost in USD** (per-model pricing table) — enough to put a real
  dollar figure on the demo, with a cache-hit-rate metric.

- **LangSmith LLM spans:** the provider SDK clients are wrapped with
  `langsmith.wrappers.wrap_anthropic / wrap_openai / wrap_gemini` (see
  `_maybe_wrap_client` in [llm_client.py](backend/app/ai/llm_client.py)), so every
  API call shows up in the LangSmith trace as a **nested LLM span with token
  counts and cost** under its node — that's what fills LangSmith's "Cost and
  Tokens" column. No-op when `LANGSMITH_TRACING` is off.

*Demo move:* run one procurement, then either (a) `tail backend/logs/workflow_execution.log`
and point at the `[TOKEN-USAGE]` line, or (b) open the run in LangSmith → expand a
node that calls the LLM (`parse_request`, `ocr_extract`, `generate_rfq_emails`,
`negotiate`, `send_po_email`) → the nested LLM span now shows tokens + cost.

> **PO email is now LLM-drafted too.** `send_po_email` calls the LLM to write a
> short, personalized opening line for the purchase-order email
> (`_draft_po_intro` in [generate_po.py](backend/app/agents/nodes/generate_po.py)),
> so that node also reports token/cost. It's best-effort — if the LLM call fails,
> the email falls back to the standard sentence, so PO delivery is never blocked.
> (The PO *PDF* is still deterministic ReportLab — we don't want an LLM inventing
> numbers on a legal document; only the human-facing cover text is generated.)

> **Note:** LangSmith only shows tokens on runs created *after* this wrapping went
> live. Older traces (like the one you were looking at) stay empty — run a fresh
> procurement to see the numbers populate.

---

## 4. Prompt caching (implemented — and actually engaging)

Large, **static** system prompts are exactly what Anthropic **prompt caching**
rewards — the same system prompt every call.

- `AnthropicProvider._build_system_param` tags the system block with
  `cache_control: {type: "ephemeral"}` when caching is enabled and the prompt is
  above the cacheable-prefix floor. → [`backend/app/ai/llm_client.py`](backend/app/ai/llm_client.py)
- Toggle: `ANTHROPIC_PROMPT_CACHING` in [`config.py`](backend/app/core/config.py) (default on).
- **The parse prompt is now ~3,900 tokens** (we inlined 8 worked few-shot
  examples into `PARSE_SYSTEM_PROMPT` — which also *improves* parse accuracy),
  so it clears the ~2,048-token floor and **caching engages for real.**

**Measured, live (via the token tracker):**

```
call 1: input=12  cache_read=3909  output=252
call 2: input=12  cache_read=3909  output=247
call 3: input=12  cache_read=3909  output=247
summary: cache_hit_rate = 0.997   (99.7%)
```

The entire 3,909-token system prompt is served from cache at ~10% of the normal
input price on every repeat call — a **~90% cut on input-token cost** and lower
latency. Verified via `usage.cache_read_input_tokens`, surfaced as
`cache_hit_rate` in `[TOKEN-USAGE]` logs and in the LangSmith LLM span.

*Demo move:* run `python -m scripts.eval_prompts` twice within 5 minutes — the
second run shows `cache hit rate: 99%` and a fraction of the input tokens.

> **How it works (say this):** the first call *writes* the prefix to cache
> (`cache_creation_input_tokens`, a one-time ~25% surcharge); every call within
> the 5-minute TTL *reads* it (`cache_read_input_tokens`) at ~1/10th the price.
> Savings scale with prompt size × call volume.

---

## 5. Prompt evaluation (implemented) — the one to run live

This is the "we treat prompts like code" proof. → [`backend/scripts/eval_prompts.py`](backend/scripts/eval_prompts.py) + golden cases in [`scripts/eval_cases/parse_cases.json`](backend/scripts/eval_cases/parse_cases.json)

- Runs the **real production prompt** (the request parser) through the **real
  code path** against 6 golden cases with concrete assertions (item count, qty,
  currency, budget, and the tricky *"Dell is a brand, not a supplier"* rule).
- Prints a **pass rate**, and — because it uses the token tracker — the **real
  token cost** of the eval run.
- **Exits non-zero if quality drops below 80%**, so it can gate CI: change a
  prompt or swap a model, re-run, and catch regressions *before* they ship.

```
$ python -m scripts.eval_prompts

ProcureGPT prompt eval  —  6 cases
prompt : app/agents/nodes/parse_request.py::PARSE_SYSTEM_PROMPT
model  : anthropic/claude-sonnet-5

  [PASS] simple-laptops
  [PASS] direct-supplier
  [PASS] brand-not-supplier
  [PASS] budget-range-currency
  [PASS] incomplete-greeting
  [PASS] multi-item

Results
  cases fully passed : 6/6  (100%)
  checks passed      : 25/25  (100%)

Cost (real, via token_tracker)
  llm calls          : 6
  tokens in/out      : 6778 / 1625
  est. cost          : $0.04471
```

*Demo move:* run it live. It's green, fast, and prints a real dollar cost —
concrete proof of both the eval discipline and the token tracker.

---

## 6. LLM layer — production hygiene

One provider-agnostic client the whole app shares. → [`backend/app/ai/llm_client.py`](backend/app/ai/llm_client.py)

| Practice | What & why |
|---|---|
| **Multi-provider abstraction** | Anthropic / OpenAI / Gemini behind one `generate()/generate_json()/chat()`; switchable at runtime. Nodes don't know which model answers. |
| **Current model IDs** | Uses valid current aliases (`claude-opus-4-8`, `claude-sonnet-5`, `claude-haiku-4-5`) — no deprecated/date-suffixed IDs. |
| **Cancellation-safe retries** | Exponential backoff on transient network errors, but `asyncio.CancelledError` is re-raised (never retried) so background workflow tasks shut down cleanly. Sits on top of the SDK's own 429/5xx retries. |
| **`stop_reason` handling** | Anthropic path logs a warning + request id on `max_tokens` truncation instead of silently returning a half-JSON that would break parsing. |
| **JSON mode** | Provider-agnostic "respond only JSON" + fence-stripping for structured extraction. (Roadmap: swap the Anthropic path to schema-guaranteed structured outputs.) |

---

## 7. Agentic engineering of the app itself (Claude Code)

The same discipline applied to *how we build* — this lands well with a tech lead
because it shows repeatable, guard-railed development, not vibes.

| Practice | What | Where |
|---|---|---|
| **Project brief for the AI** | `CLAUDE.md` — architecture, conventions, the "keep these 3 files in sync" rule | [`CLAUDE.md`](CLAUDE.md) |
| **Machine-local overrides** | `CLAUDE.local.md` — local paths, run habits, demo runbook (gitignored) | `CLAUDE.local.md` |
| **Guardrail hook (policy as code)** | PreToolUse hook **blocks** writing a live `.env` or any string that looks like an API key — the AI *cannot* leak a secret | [`.claude/hooks/protect_secrets.py`](.claude/hooks/protect_secrets.py) |
| **Auto-format hook** | PostToolUse hook runs `ruff` on every edited Python file so changes land style-clean | [`.claude/hooks/ruff_format.py`](.claude/hooks/ruff_format.py) |
| **Reusable skill** | `add-agent-node` skill encodes the four-file sync procedure for adding a graph node, so it's done correctly every time | [`.claude/skills/add-agent-node/SKILL.md`](.claude/skills/add-agent-node/SKILL.md) |

*Demo move:* show the guardrail — ask the AI to write a key into `.env` and watch
the hook block it (exit code 2 with a reason).

---

## 8. What we deliberately DON'T use (and why that's the right call)

Signals judgment, not gaps:

- **No open-ended tool-calling agent loop** — the flow is a fixed pipeline; a
  code-orchestrated graph is more reliable and debuggable than letting the model
  choose control flow.
- **No external vector DB (Pinecone/pgvector)** — supplier count is small;
  in-process cosine over precomputed embeddings is simpler and fast enough. Easy
  to swap later behind `vector_search.py`.
- **No server-side file execution / Files API** — OCR (poppler+Tesseract) and PO
  PDF generation (ReportLab) run locally; no need to round-trip files through a model.

---

## 9. Five-minute talk track

1. **"It's an agent graph, not a script."** Open `orchestrator.py`; point at the
   12 nodes, the conditional routing, and the two `interrupt` points. Explain the
   SQLite checkpointer = a workflow survives restarts while it waits days for a supplier.
2. **"Vendor matching is RAG."** Open `vector_search.py` — embeddings + cosine, hybrid with a category filter.
3. **"We see every token and dollar."** Run a workflow; tail the log; show `[TOKEN-USAGE]`.
4. **"We cache prompts — and we know when it does/doesn't help."** Show `_build_system_param` + the honest threshold caveat.
5. **"We evaluate prompts like code."** Run `python -m scripts.eval_prompts` live — green, with real cost, CI-gateable.
6. **"Same rigor in how we build it."** Trigger the secret-blocking hook; show the `add-agent-node` skill.

## 10. Glossary (say these with confidence)

- **Agentic workflow** — multi-step task driven by a graph of LLM-backed steps with control flow and human-in-the-loop pauses.
- **RAG (retrieval-augmented generation)** — retrieve relevant context (here: suppliers via vector similarity) and feed it into generation.
- **Embedding / vector similarity** — text → dense vector; cosine similarity measures semantic closeness.
- **Prompt caching** — reuse a static prompt prefix server-side to cut cost (~90%) and latency on repeat calls.
- **Token accounting / cost observability** — measuring input/output/cached tokens per call and per run to control spend.
- **Prompt evaluation (evals)** — automated, assertion-based scoring of prompt output against golden cases; gates regressions.
- **Human-in-the-loop / interrupt** — the graph pauses and hands control to a person (or an external event) before continuing.
- **Checkpointer** — durable persistence of graph state so a paused run resumes exactly where it stopped, even after a restart.
