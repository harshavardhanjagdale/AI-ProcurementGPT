# ProcureGPT — Technical Architecture & Deep Dive

> A single, technical, end-to-end explanation of how the system works: every agent/node, which file
> runs it, where the workflow pauses, how OCR turns a PDF into structured data, what generates the PO
> PDF, how the LLM layer is wired, and the Claude-API best practices applied and recommended.
>
> Audience: an engineer who wants to understand the system precisely, not marketing.

---

## 1. The 10,000-ft view

ProcureGPT automates the full RFQ → quote → PO lifecycle. A user types a need in natural language;
a **LangGraph state machine** (a graph of "agent" nodes) drives it: parse the request → find
suppliers → draft & send RFQ emails → wait for supplier replies → OCR their quote PDFs → score/rank
them → ask the human to approve/negotiate/cancel → generate & email a purchase-order PDF.

| Layer | Tech | Where |
|---|---|---|
| Frontend | Next.js 15 (App Router), React 19, TypeScript, Tailwind, Zustand | `frontend/src/**` |
| API | FastAPI (async), JWT auth | `backend/app/api/v1/**` |
| Orchestration | **LangGraph** state machine + SQLite checkpointer | `backend/app/agents/**`, `backend/app/workflows/**` |
| LLM | Multi-provider client (Anthropic / OpenAI / Gemini) | `backend/app/ai/llm_client.py` |
| OCR | pdf2image (poppler) → Tesseract → LLM extraction | `backend/app/ocr/**` |
| Vector search | sentence-transformers + cosine similarity | `backend/app/ai/vector_search.py`, `embeddings.py` |
| PDF generation | ReportLab | `backend/app/utils/pdf_generator.py` |
| Email | SMTP (aiosmtplib) + IMAP (aioimaplib) | `backend/app/email/**`, `services/email_service.py` |
| Data | MySQL 8 via SQLAlchemy async (ORM) | `backend/app/models/**`, `repositories/**` |
| Tracing | LangSmith (env-driven) | env vars, auto-instruments LangGraph |

**Layering rule (backend):** `api/v1/*` (routes) → `services/*` (business logic) → `repositories/*`
(SQLAlchemy queries) → `models/*` (ORM). LangGraph nodes call services/repositories directly.

---

## 2. How many "agents", and what each one is

There is **one compiled LangGraph** (`app/agents/orchestrator.py::build_procurement_workflow`) with
**12 nodes**. Each node is a plain async Python function in `app/agents/nodes/`. "Agent" in the UI is a
cosmetic label (`Parser Agent`, `OCR Agent`, …); technically each node is a function that reads the
shared `ProcurementState` (a `TypedDict` in `app/agents/state.py`) and returns a partial state update.

| # | Node name (`current_step`) | File | What it actually does | UI label |
|---|---|---|---|---|
| 1 | `parse_request` | `nodes/parse_request.py::parse_and_validate` | **Merged** node: LLM parses the free-text into a structured RFQ (items, qty, budget, categories, direct-supplier), then validates it (needs ≥1 product) | Parser Agent |
| 2 | `create_rfq_record` | `nodes/create_rfq.py` | Inserts the `rfqs` + `rfq_items` rows, assigns `RFQ-YYYY-NNNNN` | RFQ Agent |
| 3 | `resolve_direct_supplier` | `nodes/direct_supplier.py` | Only on the "buy from X" path — looks up the named supplier | Vendor Agent |
| 4 | `select_vendors` | `nodes/select_vendors.py` | Embeds the RFQ text, cosine-ranks suppliers, links top-K to the RFQ | Vendor Agent |
| 5 | `generate_rfq_emails` | `nodes/generate_rfq.py` | LLM drafts an RFQ email per selected supplier | Email Agent |
| 6 | `send_rfq_emails` | `nodes/send_emails.py` | Sends the RFQ emails via SMTP | Email Agent |
| 7 | `await_supplier_replies` | `nodes/await_replies.py` | **Interrupt point** — graph pauses here until a reply arrives | Inbox Agent |
| 8 | `ocr_extract` | `nodes/process_ocr.py::ocr_extract` | **Merged** node: OCR the attachment → analyze/rank quotes → build the recommendation | OCR Agent |
| 9 | `user_decision_gate` | `nodes/user_decision.py` | **Interrupt point** — graph pauses for approve/negotiate/cancel | Human |
| 10 | `negotiate_with_suppliers` | `nodes/negotiate.py` | LLM drafts + sends a counter-offer email, records a `negotiations` row | Negotiation Agent |
| 11 | `generate_purchase_order` | `nodes/generate_po.py::generate_purchase_order` | Creates the PO rows **and generates the PO PDF** (ReportLab) | PO Agent |
| 12 | `send_po_email` | `nodes/generate_po.py::send_po_email` | Emails the PO (with the PDF attached) to the supplier | Email Agent |

> **Why some steps are "merged".** `parse_request` combines what used to be two nodes (parse +
> validate), and `ocr_extract` combines three (OCR + analyze + recommend). They're merged so LangSmith
> traces and the UI progress bar stay compact. Internally each merged node just calls the original
> functions in sequence — the sub-functions (`parse_user_request`, `validate_rfq_data`,
> `process_attachments`, `analyze_quotations`, `present_recommendation`) still exist and are composed.

### The graph edges (control flow)

```
START → parse_request ──(route_after_validation)──▶ create_rfq_record          (normal)
                        ├─▶ resolve_direct_supplier ─▶ create_rfq_record        ("buy from X")
                        └─▶ END                                                 (request incomplete → ask user)

create_rfq_record → select_vendors ──(route_after_vendor_selection)──▶ generate_rfq_emails
                                     └─▶ END                                    (no supplier matched → stop, re-ask)

generate_rfq_emails → send_rfq_emails → await_supplier_replies    ⏸ interrupt_after
await_supplier_replies → ocr_extract ──(route_after_ocr)──▶ user_decision_gate  ⏸ interrupt_before
                                       └─▶ await_supplier_replies               (reply had no readable quote → keep waiting)

user_decision_gate ──(route_user_decision)──▶ generate_purchase_order           (approve)
                     ├─▶ negotiate_with_suppliers                               (negotiate)
                     └─▶ END                                                    (cancel)

negotiate_with_suppliers ──(route_negotiation_result)──▶ await_supplier_replies (loop: wait for counter-reply)
                           ├─▶ ocr_extract                                      (re-present)
                           └─▶ generate_purchase_order                         (accepted)

generate_purchase_order → send_po_email → END
```

### Where the workflow STOPS (this is the crux)

LangGraph is compiled with **two interrupt points** (`orchestrator.py::init_procurement_graph`):

- `interrupt_after=["await_supplier_replies"]` — after the graph reaches "waiting for replies", it
  **pauses and returns control**. It does not busy-wait. The run literally ends; the checkpoint is
  saved to disk. It resumes only when an external event (a supplier email) re-invokes the graph.
- `interrupt_before=["user_decision_gate"]` — after `ocr_extract` produces a recommendation, the
  graph pauses **before** the human-decision node and waits for the user to click Approve/Negotiate/Cancel.

So a single procurement is not one long-running function. It's a series of short graph invocations
separated by real-world waits (minutes to days), with the state persisted between them.

### State survives restarts (persistent checkpointer)

The graph is compiled with an **`AsyncSqliteSaver`** checkpointer writing to
`backend/data/langgraph_checkpoints.sqlite` (`orchestrator.py`). Each `WorkflowSession` row stores a
`langgraph_thread_id`; that thread id is the checkpoint key. Because it's on disk (not the in-memory
`MemorySaver`), a paused workflow survives a backend restart/redeploy — critical, since it may sit at
`await_supplier_replies` for days.

---

## 3. Two ways the same graph is driven

There is one graph but two "driver" services (both in `app/workflows/`):

1. **`session_workflow.py::SessionWorkflowService`** — the actively used path. Backs the chat
   workspace (`/api/v1/workflow/*`, frontend `/dashboard/ai-chat`). It **streams** the graph
   (`graph.astream(..., stream_mode="updates")`) and, after each node completes, commits that node's
   progress (step status, a timeline event, and a chat message) to MySQL via its own short-lived DB
   session. The frontend polls every ~3s, so the workflow tree and chat "light up" node-by-node live.
2. **`procurement_workflow.py::ProcurementWorkflowService`** — the older dashboard/`/rfqs` path;
   thin `ainvoke`/`aget_state` wrapper. Still present, less used.

`STEP_PROGRESS_MAP` / `STEP_AGENT_MAP` in `session_workflow.py` and `WORKFLOW_STEPS_TEMPLATE` in
`api/v1/workflows.py` are the source of truth for step ordering/labels and must stay in sync with the
node names in `orchestrator.py`.

### Resuming after a supplier reply (three entry points, one path)

A session parked at `await_supplier_replies` is resumed when an email arrives, via any of:

- `email/background_worker.py` — polls IMAP every 60s (`EMAIL_PROCESSING_MODE=polling|both`).
- `api/v1/webhooks.py` — real-time; an email provider POSTs `/api/v1/webhook/email-arrived`.
- `api/v1/workflows.py::check_session_emails` — the manual "check now" button (mail icon).

All three: save the inbound email/attachment rows → then call
`session_workflow_service.resume_after_reply(session_id, thread_id)` → which streams `ocr_extract`
onward. The link from email → session is `WorkflowSession.rfq_id` (populated during
`create_rfq_record`); the worker matches an inbound email's RFQ to a waiting session by that field.

---

## 4. The OCR pipeline — exactly how a PDF becomes structured data

Entry: the `ocr_extract` node → `services/ocr_service.py` → `services/quotation_service.py` →
`ocr/pipeline.py::OCRPipeline.process_pdf`. The four stages (`ocr/pipeline.py`):

1. **PDF → images.** `ocr/pdf_converter.py` uses **`pdf2image.convert_from_path`** at **300 DPI**,
   output format **PNG**, one PIL `Image` per page. This requires **poppler** installed on the host
   (`choco install poppler` on Windows / `apt install poppler-utils` on Linux). Yes — the PDF is
   rasterized to images first; OCR runs on the images, not the PDF text layer.
2. **Images → raw text.** `ocr/tesseract_engine.py` runs **`pytesseract.image_to_string`** on each
   PIL image with config **`--oem 3 --psm 6`** (OEM 3 = default LSTM engine; PSM 6 = assume a single
   uniform block of text), language `eng`. Per-page text is concatenated with `--- Page N ---`
   markers. (A `extract_with_confidence` variant using `image_to_data` also exists for per-word
   confidence, but the main flow uses plain `image_to_string`.)
3. **Raw text → structured JSON.** `ocr/structured_extractor.py::extract_quotation_data` sends the
   OCR text to the **LLM** (`llm_client.generate_json`) with a prompt describing the target schema
   (supplier, currency, `items[]` with `product_name`/`unit_price`/`quantity`/`total_price`,
   `subtotal`, `tax_percent`/`tax_amount`, `total_amount`, delivery/warranty/payment terms). This is
   where messy OCR text becomes clean fields — the LLM handles layout variance the regex never could.
4. **Validation.** `validate_extraction` recomputes totals from line items and attaches a
   `_validation` block (`confidence`, `issues` like `total_discrepancy_15.3%`, `calculated_total`),
   so downstream code knows how much to trust the numbers.

The extracted dict is persisted by `quotation_service.py::_create_quotation_from_extraction` as a
`quotations` row + `quotation_items` rows. A supplier's **revised** quote (after a negotiation round)
is stored as a **new** quotation row with an incremented `negotiation_round` (keyed off distinct
inbound emails), so the original and revised quotes are both preserved and comparable.

**Poppler/Tesseract are external system binaries** — they are the two non-pip dependencies OCR needs.
If OCR ever returns empty text, it's almost always a missing poppler (PDF→image failed) or a
scanned-image quality issue.

---

## 5. Vendor selection — semantic search, not keyword match

`nodes/select_vendors.py` builds a query string from the RFQ (`title + description + categories`) and
calls `ai/vector_search.py::rank_suppliers_by_similarity`:

- **Embeddings** (`ai/embeddings.py`) use **sentence-transformers `all-MiniLM-L6-v2`** (384-dim).
  Supplier embeddings are precomputed and stored as a `BLOB` on the `suppliers` row (see
  `scripts/generate_embeddings.py`); if missing, they're generated on the fly.
- Ranking is plain **cosine similarity** (numpy) between the query embedding and each supplier
  embedding; top-K (default 5) are returned and linked to the RFQ (`rfq_suppliers`).
- There's a DB pre-filter by category first; if nothing matches, it falls back to all active
  suppliers, then ranks. If still zero, `route_after_vendor_selection` sends the graph to END and the
  session re-opens for a new requirement.

---

## 6. LLM layer — multi-provider, one interface

`app/ai/llm_client.py` is a small provider-abstraction the whole app shares via the module singleton
`llm_client`:

- **Providers:** `AnthropicProvider` (Anthropic SDK `AsyncAnthropic`), `OpenAIProvider`
  (`AsyncOpenAI`), `GeminiProvider` (`google.genai`). Selected by `LLM_PROVIDER` in `.env`; switchable
  at runtime via `set_provider()`. Every consumer calls the same `generate()` / `generate_json()` /
  `chat()`, so nodes/OCR don't know or care which model is behind them.
- **Config:** `.env` sets `ANTHROPIC_MODEL=claude-sonnet-5` (current). The provider dropdown
  (`AVAILABLE_MODELS`) now lists valid current Anthropic IDs: `claude-opus-4-8`, `claude-sonnet-5`,
  `claude-haiku-4-5`.
- **JSON mode:** `generate_json` appends a "respond with ONLY JSON" instruction and strips markdown
  fences, then `json.loads`. Provider-agnostic; works across all three.
- **Retries:** an outer provider-agnostic retry (exp backoff) on transient network/IO errors, on top
  of each SDK's own built-in retries (Anthropic/OpenAI retry 429/5xx/connection automatically).

> Where the raw Anthropic SDK is used: only inside `AnthropicProvider._call` — a single
> `client.messages.create(model, max_tokens, system, messages)`. Everything else goes through the
> abstraction.

---

## 7. PDF generation — the purchase order document

`app/utils/pdf_generator.py::POPDFGenerator` uses **ReportLab** (`SimpleDocTemplate` + `platypus`
flowables — `Table`, `Paragraph`, `HRFlowable`). It renders a branded A4 PO: header, PO/RFQ/date
table, supplier block, an items table (`# / Item / Qty / Unit Price / Total` with a TOTAL row),
terms & conditions, signature line, footer. Output is written to
`backend/uploads/purchase_orders/<PO-NUMBER>.pdf`.

It's invoked from `nodes/generate_po.py::generate_purchase_order` (in a thread via `asyncio.to_thread`
so it doesn't block the event loop), the path is saved on `purchase_orders.pdf_path`, and
`send_po_email` attaches that file to the supplier email through `email_service.send_purchase_order_email`.

---

## 8. Email in/out

- **Outbound** (RFQ, negotiation, PO): `services/email_service.py` renders an HTML template
  (`email/templates/*.html`) and sends via **`aiosmtplib`** (`email/smtp_client.py`). Every send also
  writes an `emails` row (`direction=outbound`).
- **Inbound** (supplier replies): the IMAP side (**`aioimaplib`**, `email/background_worker.py` /
  `services/email_service.py::check_inbox_for_replies`) matches replies to an RFQ by the
  `RFQ-YYYY-NNNNN` token in the subject, saves the email + PDF attachment, and triggers the resume.
- **Mode** is controlled by `EMAIL_PROCESSING_MODE` (`polling` | `webhook` | `both`).

---

## 9. Persistence & tracing

- **MySQL** (SQLAlchemy async, `aiomysql`): domain tables (`rfqs`, `rfq_items`, `suppliers`,
  `quotations`, `quotation_items`, `negotiations`, `purchase_orders`, `emails`, …) plus the chat/UI
  tables (`workflow_sessions`, `workflow_steps`, `workflow_events`, `conversation_messages`). IDs are
  UUID4 strings; timestamps are IST (`app/models/base.py::ist_now`).
- **SQLite checkpointer** (LangGraph): the graph's own channel state per thread, separate from MySQL.
- **LangSmith:** enabled purely by env vars loaded at startup (`main.py` calls `load_dotenv()`):
  `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`. LangGraph auto-emits a trace
  tree per invocation (one root `LangGraph` run with each node as a child run). No code changes are
  needed — but note the raw Anthropic calls inside nodes are **not** wrapped as nested LLM spans (see
  recommendations below).

---

## 10. Claude API best practices — applied & recommended

The Claude/Anthropic guidance below is mapped specifically to this codebase. "Pre-LLM" = things you
do to the request before it's sent; "Post-LLM" = things you do with the response; "Hooks" =
lifecycle/middleware you register around calls.

### Applied in this change

| Practice | What & why |
|---|---|
| **Current model IDs** | Replaced deprecated/invalid IDs (`claude-sonnet-4-20250514`, the non-existent `claude-haiku-4-20250414`, `claude-opus-4-20250514`) with current aliases (`claude-opus-4-8`, `claude-sonnet-5`, `claude-haiku-4-5`). Never append date suffixes to aliases. |
| **Cancellation-safe retries** | Removed `asyncio.CancelledError` from the retry set + added an explicit re-raise. Retrying a cancellation fights task shutdown (this app runs the workflow as fire-and-forget background tasks that get cancelled on shutdown/timeout). |
| **Lean on SDK retries** | Documented that the Anthropic/OpenAI SDKs already retry 429/5xx/connection with backoff (`max_retries` default 2); the outer loop is a second net, not the primary. |

### Recommended next (with concrete hooks into this repo)

**Pre-LLM.**
- **Structured outputs instead of "respond only JSON" + fence-stripping.** For the Anthropic path,
  `parse_request`, `ocr_extract` (extractor), and `analyze_quotations` all want strict JSON. Anthropic
  supports `output_config={"format": {"type":"json_schema","schema":{…, "additionalProperties":false}}}`
  (or `client.messages.parse()` with a Pydantic model) which *guarantees* schema-valid output — no
  fence stripping, no `JSONDecodeError` fallback. Add a `generate_structured(schema)` method on
  `AnthropicProvider` and have those three call sites pass a schema. (Keep the prompt-based path for
  OpenAI/Gemini.)
- **Prompt caching** for large, static system prompts. `cache_control:{type:"ephemeral"}` on the
  system block cuts cost ~90% on repeats. **Caveat for this repo:** the current system prompts are
  small (~400–800 tokens) and the min cacheable prefix for `claude-sonnet-5` is ~2048 tokens, so
  caching silently won't engage until prompts grow (e.g. if you inline few-shot examples). Verify with
  `usage.cache_read_input_tokens`.
- **Token counting** before big requests (`client.messages.count_tokens`) if you ever feed large OCR
  text — use it for cost estimation/guardrails rather than `tiktoken` (which mis-counts Claude tokens).

**Post-LLM.**
- **Handle `stop_reason`.** `AnthropicProvider._call` concatenates text blocks but never inspects
  `stop_reason`. Add branches for `max_tokens` (truncated → raise/retry with higher cap) and
  `refusal` (return a clean error rather than empty text). Cheap, prevents silent bad extractions.
- **Log `_request_id` on failure.** Every Anthropic response/error carries `response._request_id`;
  logging it makes support tickets to Anthropic traceable.

**Hooks / lifecycle.**
- **Wrap the Anthropic client for LangSmith LLM spans.** Right now LangSmith shows the graph nodes but
  not per-call token/cost detail, because nodes call the raw SDK. Wrapping with
  `langsmith.wrappers.wrap_anthropic(AsyncAnthropic(...))` inside `AnthropicProvider` adds nested LLM
  spans (tokens, latency, cost) under each node — big observability win, ~1 line.
- **Streaming for large outputs.** Not needed today (`max_tokens` ≤ 3000), but if you raise output
  size, the SDK requires streaming above ~16K tokens; use `messages.stream()` + `.get_final_message()`.
- **Tool use vs. free-text JSON.** The current design (LLM returns JSON we parse) is a *workflow*, not
  an *agent* — which is the right call here (deterministic, code-controlled steps). Don't convert nodes
  to Claude tool-calling agents; reserve tool use for genuinely open-ended sub-tasks.

### What this system deliberately does NOT use (and why that's correct)

- **No Managed Agents / agentic tool loops** — the procurement flow is a fixed pipeline; a
  code-orchestrated LangGraph is the right tier, not a model-driven agent.
- **No Anthropic Files API / server-side code execution** — OCR is done locally (poppler+Tesseract)
  and PDFs are generated locally (ReportLab); no need to round-trip files through the model.
- **No prompt caching yet** — prompts are below the cache threshold (documented above).

---

## 11. Quick file map (where to look)

```
backend/app/
  agents/
    orchestrator.py        # builds/compiles the 12-node graph; interrupts; SQLite checkpointer
    state.py               # ProcurementState TypedDict (the shared state)
    nodes/                 # one file per node (parse_request, select_vendors, process_ocr, negotiate, generate_po, …)
  workflows/
    session_workflow.py    # streaming driver + per-node DB persistence (the live UI path)
    procurement_workflow.py# older ainvoke driver
  ai/
    llm_client.py          # multi-provider LLM abstraction (Anthropic/OpenAI/Gemini)
    embeddings.py          # sentence-transformers all-MiniLM-L6-v2
    vector_search.py       # cosine-similarity supplier ranking
  ocr/
    pipeline.py            # PDF→images→text→LLM extract→validate
    pdf_converter.py       # pdf2image @300dpi (needs poppler)
    tesseract_engine.py    # pytesseract --oem 3 --psm 6
    structured_extractor.py# LLM turns OCR text into quotation JSON + validation
  utils/pdf_generator.py   # ReportLab PO PDF
  services/                # email_service, ocr_service, quotation_service, negotiation_service, …
  api/v1/                  # workflows.py (chat/session API), webhooks.py, negotiations.py, …
  email/                   # smtp_client, background_worker (IMAP poll), templates/
  models/ • repositories/  # SQLAlchemy ORM + queries
```

---

## 12. One-paragraph summary

A user's sentence enters the chat API, which fires a background task that **streams** a 12-node
LangGraph. The graph parses the request (LLM), creates an RFQ, semantically matches suppliers
(sentence-transformers + cosine), drafts and SMTP-sends RFQ emails, then **pauses** (checkpoint saved
to SQLite). When a supplier replies (IMAP poll / webhook / manual), the graph resumes, converts the
attached PDF to images (pdf2image @300dpi / poppler), OCRs them (Tesseract), and asks the LLM to turn
that text into a validated quotation JSON, which it scores and ranks. It **pauses again** for the
human to Approve / Negotiate / Cancel. Approve → it builds a purchase-order PDF (ReportLab) and emails
it to the supplier; Negotiate → it emails a counter-offer and loops back to waiting. All LLM calls go
through one provider-agnostic client (Anthropic/OpenAI/Gemini), and the whole graph is traced in
LangSmith.
