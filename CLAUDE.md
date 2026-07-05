# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ProcureGPT is an AI-powered procurement automation system. A user describes a purchase need in natural language; a LangGraph agent graph parses the request, selects suppliers, drafts and sends RFQ emails, OCRs supplier quote attachments as they arrive, scores/ranks quotations, waits for a human approve/negotiate/cancel decision, and generates a purchase order PDF.

- **Backend**: FastAPI + SQLAlchemy (async) + MySQL, LangGraph for agent orchestration, Tesseract/pdf2image for OCR, OpenAI for LLM calls, SMTP/IMAP for email.
- **Frontend**: Next.js 15 (App Router) + React 19 + TypeScript + Tailwind + shadcn/ui-style components + Zustand.

## Commands

### Backend (`backend/`)

```bash
python -m venv venv && venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env                             # then edit values
python -m scripts.init_db                          # create tables
python -m scripts.seed_suppliers                   # seed sample suppliers
uvicorn app.main:app --reload --port 8000
```

Requires MySQL 8+ and Redis running locally (no `docker-compose.yml` is currently checked in, despite `backend/README.md` referencing one — start MySQL/Redis manually or add one).

Other useful scripts in `backend/scripts/`:
- `generate_embeddings.py` — batch-generate supplier embeddings
- `check_status.py`, `check_workflow.py` — inspect workflow/session state from the CLI
- `email_listener.py` — standalone IMAP IDLE listener for local dev

Alembic migrations: `alembic revision --autogenerate -m "..."` / `alembic upgrade head` (run from `backend/`, config in `alembic.ini`).

Tests: `pytest` is configured in `pyproject.toml` (`testpaths = ["tests"]`, `asyncio_mode = "auto"`) but no `tests/` directory currently exists in the repo — there is no test suite to run yet.

Lint: `ruff` is configured (`target-version = "py312"`, `line-length = 100`) but no ruff invocation is wired into a script; run `ruff check .` from `backend/` directly.

### Frontend (`frontend/`)

```bash
npm install
npm run dev      # next dev
npm run build
npm run start
npm run lint      # next lint
```

Frontend expects the API at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api/v1`).

## Architecture

### Two parallel ways to drive the same LangGraph

There is a single compiled LangGraph state machine (`app/agents/orchestrator.py::procurement_graph`), but two different callers drive it, backing two different frontend surfaces:

1. **`app/workflows/procurement_workflow.py`** (`ProcurementWorkflowService`) — thin wrapper around `procurement_graph.ainvoke`/`aget_state`, keyed by `workflow_id` as the LangGraph `thread_id`. Used by the older `/api/v1/rfqs` + `(dashboard)` frontend flow.
2. **`app/workflows/session_workflow.py`** (`SessionWorkflowService`) — bridges the same graph to persistent `WorkflowSession` / `WorkflowStep` / `WorkflowEvent` / `ConversationMessage` DB rows (see `app/models/workflow_*.py`, `conversation_message.py`) for a ChatGPT-style UI. Used by `app/api/v1/workflows.py` (mounted at `/api/v1/workflow`) and the `frontend/src/app/workspace` chat surface. This is the actively-developed path — `STEP_PROGRESS_MAP` / `STEP_AGENT_MAP` in this file are the source of truth for step ordering and must stay in sync with `orchestrator.py` node names and `WORKFLOW_STEPS_TEMPLATE` in `workflows.py`.

When adding/renaming a graph node, update all three: `orchestrator.py`, `STEP_PROGRESS_MAP`/`STEP_AGENT_MAP` in `session_workflow.py`, and `WORKFLOW_STEPS_TEMPLATE` in `api/v1/workflows.py`.

### LangGraph state machine (`app/agents/`)

- `state.py` defines `ProcurementState` (TypedDict) — the single shared state threaded through every node.
- `orchestrator.py::build_procurement_workflow()` wires up nodes/edges; `compile_procurement_workflow()` compiles with `MemorySaver` (in-memory checkpointer — state does not survive a process restart) and sets interrupt points:
  - `interrupt_before=["user_decision_gate"]` — pauses for the human approve/negotiate/cancel decision.
  - `interrupt_after=["await_supplier_replies"]` — pauses until a supplier email arrives.
- Nodes live in `app/agents/nodes/`, one file per node (`parse_request.py`, `validate_rfq.py`, `select_vendors.py`, `direct_supplier.py`, `generate_rfq.py`, `send_emails.py`, `await_replies.py`, `process_ocr.py`, `analyze_quotes.py`, `user_decision.py`, `negotiate.py`, `generate_po.py`).
- Flow branches after validation into either a multi-vendor path (`select_vendors`) or a direct-supplier path (`resolve_direct_supplier`, when the user names a specific vendor) — both converge back into RFQ generation → send → await replies.
- Negotiation is a loop: `negotiate_with_suppliers` routes (via `route_negotiation_result`) back to `await_supplier_replies`, or on to `present_recommendation`/`generate_purchase_order`.

### Resuming a paused graph (email arrival)

A `WorkflowSession.langgraph_thread_id` is the LangGraph `thread_id`. Three independent code paths can resume a session sitting at `await_supplier_replies`, and they must all keep the `WorkflowSession`/`WorkflowStep`/`WorkflowEvent`/`ConversationMessage` rows and the LangGraph checkpoint state consistent:
- `app/email/background_worker.py` — polls IMAP every 60s (`EMAIL_PROCESSING_MODE=polling`/`both`), started in `main.py` startup unless mode is `webhook`.
- `app/api/v1/webhooks.py::webhook_email_arrived` — real-time path for `EMAIL_PROCESSING_MODE=webhook`/`both`; an external email provider POSTs to `/api/v1/webhook/email-arrived` with `X-Webhook-Token` auth, and this directly calls `procurement_graph.ainvoke(None, config=...)` to resume.
- `app/api/v1/workflows.py::check_session_emails` — manual "check now" endpoint the frontend can call, which calls `email_worker.poll_once()`.

`EMAIL_PROCESSING_MODE` (`polling` | `webhook` | `both`, in `.env`) controls which of the automatic paths run.

### OCR pipeline (`app/ocr/`)

`pipeline.py::OCRPipeline.process_pdf` chains: `pdf_converter` (pdf2image → PIL images) → `tesseract_engine` (per-page OCR text) → `structured_extractor` (LLM call to turn raw OCR text into structured quotation JSON). The `process_attachments` graph node calls this per email attachment.

### Layering convention (backend)

`api/v1/*` (routes) → `services/*` (business logic) → `repositories/*` (SQLAlchemy queries) → `models/*` (ORM). Pydantic DTOs live in `schemas/*`, separate from ORM models in `models/*`. New endpoints should follow this same chain rather than querying the DB directly from a route.

- Auth: JWT via `app/core/security.py`; `get_current_user`/`get_admin_or_pm`/`get_admin` dependencies in `app/core/dependencies.py` gate routes. Roles: `admin`, `procurement_manager`, `viewer`.
- DB session: always obtained via `Depends(get_db)` (`app/database/session.py`), which commits on success / rolls back on exception.
- All model timestamps use **IST (UTC+5:30)**, not UTC — see `ist_now()` in `app/models/base.py` (`utc_now()` also exists for legacy/back-compat code paths; prefer `ist_now()` in new code to match the rest of the schema).
- IDs are UUID4 strings (`generate_uuid()` in `app/models/base.py`), not auto-increment ints.

### Frontend structure

Two separate route trees hit the same backend:
- `frontend/src/app/(dashboard)/dashboard/**` — traditional CRUD screens (RFQs, suppliers, quotations, purchase orders, negotiations) talking to the REST resource endpoints.
- `frontend/src/app/workspace/**` — the chat-driven workspace UI (`ChatPanel`, `WorkflowGraph`, `EventTimeline`, `WorkspaceSidebar` in `components/workspace/`) driving `session_workflow.py` via `/api/v1/workflow/*`.

`services/*.ts` are thin axios wrappers per resource, all routed through `services/api.ts`, which attaches the JWT from `localStorage` and redirects to `/login` on a 401.

## Security note

`backend/.env.example` currently contains what appear to be live credentials (an OpenAI API key and a Gmail SMTP app password) rather than placeholder values. Treat this as sensitive — do not commit real secrets into `.env.example`, and rotate these credentials if they are in fact live.
