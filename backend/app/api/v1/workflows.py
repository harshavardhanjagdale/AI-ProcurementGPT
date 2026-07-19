"""
Workflow Sessions API - ChatGPT-like conversation management for procurement workflows.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.workflow_session import WorkflowSession
from app.models.workflow_step import WorkflowStep
from app.models.workflow_event import WorkflowEvent
from app.models.conversation_message import ConversationMessage
from app.models.base import generate_uuid
from app.models.base import utc_now, ist_now

logger = logging.getLogger(__name__)

router = APIRouter()

WORKFLOW_STEPS_TEMPLATE = [
    {"name": "parse_request", "display_name": "Understand Request", "agent": "Parser Agent", "order_index": 0},
    {"name": "create_rfq_record", "display_name": "Create RFQ", "agent": "RFQ Agent", "order_index": 1},
    {"name": "resolve_direct_supplier", "display_name": "Direct Supplier", "agent": "Vendor Agent", "order_index": 2},
    {"name": "select_vendors", "display_name": "Select Vendors", "agent": "Vendor Agent", "order_index": 3},
    {"name": "generate_rfq_emails", "display_name": "Draft Emails", "agent": "Email Agent", "order_index": 4},
    {"name": "send_rfq_emails", "display_name": "Send Emails", "agent": "Email Agent", "order_index": 5},
    {"name": "await_supplier_replies", "display_name": "Await Replies", "agent": "Inbox Agent", "order_index": 6},
    {"name": "ocr_extract", "display_name": "OCR Extract", "agent": "OCR Agent", "order_index": 7},
    {"name": "user_decision_gate", "display_name": "Your Decision", "agent": "Human", "order_index": 8},
    {"name": "negotiate_with_suppliers", "display_name": "Negotiation", "agent": "Negotiation Agent", "order_index": 9},
    {"name": "generate_purchase_order", "display_name": "Purchase Order", "agent": "PO Agent", "order_index": 10},
    {"name": "send_po_email", "display_name": "Send PO", "agent": "Email Agent", "order_index": 11},
]


class NewSessionRequest(BaseModel):
    title: str | None = None


class ContinueSessionRequest(BaseModel):
    message: str


class RenameSessionRequest(BaseModel):
    title: str


class DecisionRequest(BaseModel):
    decision: str  # "approve" | "negotiate" | "cancel"
    target_price: float | None = None  # required when decision == "negotiate"
    quotation_id: str | None = None  # the quotation the user selected (approve → PO / negotiate)


# ─────────────────────────────────────────────────────────────
# LIST / GET sessions
# ─────────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all workflow sessions for current user (sidebar data)."""
    query = (
        select(WorkflowSession)
        .where(WorkflowSession.user_id == current_user.id)
        .order_by(WorkflowSession.updated_at.desc())
    )
    if status:
        query = query.where(WorkflowSession.status == status)

    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    sessions = list(result.scalars().all())

    return {
        "items": [_session_summary(s) for s in sessions],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get full session details including steps."""
    session = await _get_session_or_404(db, session_id, current_user.id)

    # Load steps
    steps_result = await db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.session_id == session_id)
        .order_by(WorkflowStep.order_index)
    )
    steps = list(steps_result.scalars().all())

    return {
        **_session_detail(session),
        "steps": [_step_data(s) for s in steps],
    }


@router.get("/{session_id}/steps")
async def get_session_steps(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get workflow steps for visualization."""
    await _get_session_or_404(db, session_id, current_user.id)

    result = await db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.session_id == session_id)
        .order_by(WorkflowStep.order_index)
    )
    steps = list(result.scalars().all())

    return {"steps": [_step_data(s) for s in steps]}


@router.get("/{session_id}/events")
async def get_session_events(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get timeline events for a session."""
    await _get_session_or_404(db, session_id, current_user.id)

    result = await db.execute(
        select(WorkflowEvent)
        .where(WorkflowEvent.session_id == session_id)
        .order_by(WorkflowEvent.created_at.desc())
        .limit(limit)
    )
    events = list(result.scalars().all())

    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "title": e.title,
                "description": e.description,
                "agent": e.agent,
                "metadata": e.metadata_json,
                "created_at": e.created_at.isoformat(),
            }
            for e in reversed(events)
        ]
    }


@router.get("/{session_id}/quotations")
async def get_session_quotations(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all quotations received for a session's RFQ, with AI scores/ranking and line items."""
    session = await _get_session_or_404(db, session_id, current_user.id)

    if not session.rfq_id:
        return {"quotations": []}

    from app.repositories.quotation_repository import QuotationRepository

    quotation_repo = QuotationRepository(db)
    quotations = await quotation_repo.get_by_rfq(session.rfq_id)

    return {"quotations": [_quotation_data(q) for q in quotations]}


@router.get("/{session_id}/chat")
async def get_session_chat(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get chat messages for a session."""
    await _get_session_or_404(db, session_id, current_user.id)

    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at.asc())
        .limit(limit)
    )
    messages = list(result.scalars().all())

    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "message_type": m.message_type,
                "metadata": m.metadata_json,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]
    }


# ─────────────────────────────────────────────────────────────
# CREATE / CONTINUE / RENAME / DELETE
# ─────────────────────────────────────────────────────────────

@router.post("/new")
async def create_session(
    data: NewSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new procurement workflow session."""
    session = WorkflowSession(
        id=generate_uuid(),
        user_id=current_user.id,
        title=data.title or "New Procurement",
        status="active",
        current_step="waiting_input",
        progress_percentage=0.0,
    )
    db.add(session)

    # Create all step placeholders
    for step_tmpl in WORKFLOW_STEPS_TEMPLATE:
        step = WorkflowStep(
            id=generate_uuid(),
            session_id=session.id,
            name=step_tmpl["name"],
            display_name=step_tmpl["display_name"],
            agent=step_tmpl["agent"],
            status="pending",
            order_index=step_tmpl["order_index"],
        )
        db.add(step)

    # Add system welcome message
    welcome = ConversationMessage(
        id=generate_uuid(),
        session_id=session.id,
        role="assistant",
        content="Hello! I'm your AI procurement assistant. Tell me what you need to purchase and I'll handle the entire process — from finding the best suppliers to generating purchase orders.\n\nExamples:\n- \"Buy 10 Dell Latitude laptops\"\n- \"Purchase 50 office chairs from ErgoSupply\"\n- \"I need 100 USB-C cables, find me the best price\"",
        message_type="text",
    )
    db.add(welcome)

    await db.flush()

    logger.info(f"[WORKFLOW] New session created: {session.id} for user {current_user.id}")

    return _session_detail(session)


STEPS_ACCEPTING_CHAT = {"waiting_input"}

STEP_CONTEXT_MESSAGES = {
    "await_supplier_replies": (
        "I'm currently waiting for supplier responses. You don't need to do anything right now — "
        "I'll notify you automatically when quotations arrive. You can also click the mail icon "
        "to manually check for replies."
    ),
    "ocr_extract": (
        "I'm processing the received quotation(s) — extracting data and analyzing them. "
        "Please wait a moment, I'll present the results shortly."
    ),
    "user_decision_gate": (
        "I'm waiting for your decision on the quotation(s). Please use the Approve, Negotiate, "
        "or Cancel buttons below to proceed."
    ),
    "negotiate_with_suppliers": (
        "Negotiation is in progress. I'm waiting for the supplier's response to our counter-offer."
    ),
    "generate_purchase_order": "I'm generating the purchase order. Please wait a moment.",
    "send_po_email": "I'm sending the purchase order to the supplier. Almost done!",
    "generate_rfq_emails": "I'm drafting the RFQ emails to send to suppliers. Please wait.",
    "send_rfq_emails": "I'm sending the RFQ emails now. This will take just a moment.",
    "select_vendors": "I'm selecting the best vendors for your requirement. Please wait.",
    "create_rfq_record": "I'm creating the RFQ record. Please wait.",
    "resolve_direct_supplier": "I'm looking up the supplier you specified. Please wait.",
}


@router.post("/{session_id}/continue")
async def continue_session(
    session_id: str,
    data: ContinueSessionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Send a message in a session to (re)drive the workflow.

    Validates that the current step actually accepts free-text user input before
    resuming the graph. Steps like await_supplier_replies or generate_purchase_order
    don't accept arbitrary chat — they return a helpful contextual message instead.
    """
    session = await _get_session_or_404(db, session_id, current_user.id)

    current_step = session.current_step or "waiting_input"

    # ── Guard: terminal sessions cannot be continued ──
    if session.status in ("completed", "cancelled"):
        reply_msg = (
            "This procurement is already complete. Please start a new procurement "
            "if you need something else."
            if session.status == "completed"
            else "This procurement was cancelled. Please start a new one."
        )
        msg = ConversationMessage(
            id=generate_uuid(),
            session_id=session_id,
            role="user",
            content=data.message,
            message_type="text",
        )
        reply = ConversationMessage(
            id=generate_uuid(),
            session_id=session_id,
            role="assistant",
            content=reply_msg,
            message_type="text",
        )
        db.add(msg)
        db.add(reply)
        await db.flush()

        steps_result = await db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.session_id == session_id)
            .order_by(WorkflowStep.order_index)
        )
        steps = list(steps_result.scalars().all())
        return {
            "message": reply_msg,
            "session": _session_detail(session),
            "steps": [_step_data(s) for s in steps],
            "current_step": session.current_step,
            "workflow_id": session.langgraph_thread_id,
        }

    # ── Guard: steps that don't accept free-text input ──
    if current_step not in STEPS_ACCEPTING_CHAT:
        context_msg = STEP_CONTEXT_MESSAGES.get(
            current_step,
            "The workflow is currently processing. Please wait for the current step to complete before sending a message."
        )
        msg = ConversationMessage(
            id=generate_uuid(),
            session_id=session_id,
            role="user",
            content=data.message,
            message_type="text",
        )
        reply = ConversationMessage(
            id=generate_uuid(),
            session_id=session_id,
            role="assistant",
            content=context_msg,
            message_type="text",
        )
        db.add(msg)
        db.add(reply)
        await db.flush()

        steps_result = await db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.session_id == session_id)
            .order_by(WorkflowStep.order_index)
        )
        steps = list(steps_result.scalars().all())
        return {
            "message": context_msg,
            "session": _session_detail(session),
            "steps": [_step_data(s) for s in steps],
            "current_step": session.current_step,
            "workflow_id": session.langgraph_thread_id,
        }

    # ── Valid: Save user message and run the workflow ──
    user_msg = ConversationMessage(
        id=generate_uuid(),
        session_id=session_id,
        role="user",
        content=data.message,
        message_type="text",
    )
    db.add(user_msg)

    # Advance the session to the first step *immediately* so the progress bar appears
    # the moment the user sends a message (the frontend hides it while at waiting_input).
    # The background run then streams the real per-node progress on top of this.
    session.status = "active"
    session.current_step = "parse_request"
    session.current_node = "parse_request"
    session.current_agent = "Parser Agent"
    session.progress_percentage = 5.0
    await db.execute(
        update(WorkflowStep)
        .where(WorkflowStep.session_id == session_id, WorkflowStep.name == "parse_request")
        .values(status="running", started_at=ist_now())
    )
    await db.flush()

    from app.workflows.session_workflow import session_workflow_service
    background_tasks.add_task(
        session_workflow_service.run_workflow, session_id, data.message, current_user.id
    )

    # Return the current (pre-run) snapshot; polling will pick up live progress.
    steps_result = await db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.session_id == session_id)
        .order_by(WorkflowStep.order_index)
    )
    steps = list(steps_result.scalars().all())

    return {
        "message": "Working on it...",
        "session": _session_detail(session),
        "steps": [_step_data(s) for s in steps],
        "current_step": session.current_step,
        "workflow_id": session.langgraph_thread_id,
    }


@router.post("/{session_id}/check-emails")
async def check_session_emails(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Manually trigger an email check for a session's RFQ. If a supplier reply is
    found, the LangGraph checkpoint is resumed (OCR, analysis, etc.) and the
    session's real post-resume state is returned.
    """
    session = await _get_session_or_404(db, session_id, current_user.id)

    if not session.rfq_id:
        return {"message": "No RFQ associated with this session yet.", "emails_found": 0}

    # Check for inbound emails for this RFQ
    from app.models.email import Email
    result = await db.execute(
        select(func.count()).select_from(Email).where(
            Email.rfq_id == session.rfq_id,
            Email.direction == "inbound",
            Email.email_type == "supplier_reply",
        )
    )
    reply_count_before = result.scalar() or 0

    # Trigger a manual inbox poll. If this session's RFQ has a reply, this also
    # resumes its LangGraph checkpoint (OCR -> analysis -> recommendation).
    from app.email.background_worker import email_worker
    await email_worker.poll_once()

    # Re-count after polling
    result = await db.execute(
        select(func.count()).select_from(Email).where(
            Email.rfq_id == session.rfq_id,
            Email.direction == "inbound",
            Email.email_type == "supplier_reply",
        )
    )
    new_replies = (result.scalar() or 0) - reply_count_before

    if new_replies > 0:
        await db.refresh(session)
        return {
            "message": f"Found {new_replies} new supplier repl{'ies' if new_replies > 1 else 'y'}! "
                       f"Now at: {session.current_step}",
            "emails_found": new_replies,
            "status": session.status,
            "current_step": session.current_step,
        }

    return {
        "message": "No supplier replies found yet. Will keep checking.",
        "emails_found": 0,
        "status": "waiting",
        "current_step": "await_supplier_replies",
    }


@router.post("/{session_id}/decision")
async def submit_session_decision(
    session_id: str,
    data: DecisionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Submit approve/negotiate/cancel once the AI recommendation is ready.

    The actual graph resume (which, for "approve", runs PDF generation and a real
    SMTP send and can take several seconds) is handed off to a background task
    rather than awaited here. Awaiting it inline previously meant that if the
    request took long enough for the browser/proxy to time out or disconnect,
    the server could cancel the in-flight request task *after* LangGraph had
    already durably completed and sent the PO, but *before* the DB sync that
    the UI actually reads ever ran — leaving the session stuck showing the old
    step even though the real-world action had already happened. The frontend
    already polls session/chat state every few seconds, so it picks up the
    result once the background task finishes syncing it.
    """
    if data.decision not in ("approve", "negotiate", "cancel"):
        raise HTTPException(status_code=400, detail="decision must be one of: approve, negotiate, cancel")

    session = await _get_session_or_404(db, session_id, current_user.id)

    if not session.langgraph_thread_id:
        raise HTTPException(status_code=400, detail="This session's workflow has not started yet.")

    thread_id = session.langgraph_thread_id

    # For "negotiate" we need a target price and the supplier we're negotiating with.
    # Build the negotiation target from the top-ranked quotation of this RFQ.
    negotiation_targets = None
    decision_label = data.decision.capitalize()
    if data.decision == "negotiate":
        if not data.target_price or data.target_price <= 0:
            raise HTTPException(status_code=400, detail="A target_price is required to negotiate.")
        from app.repositories.quotation_repository import QuotationRepository

        quotes = await QuotationRepository(db).get_by_rfq(session.rfq_id) if session.rfq_id else []
        top = None
        # Prefer the quotation the user explicitly selected; otherwise fall back to the
        # supplier's *latest* quotation (highest negotiation round) as the baseline.
        if data.quotation_id:
            top = next((q for q in quotes if q.id == data.quotation_id), None)
        if top is None:
            for q in quotes:
                if top is None or (q.negotiation_round or 0) > (top.negotiation_round or 0):
                    top = q
        if not top:
            raise HTTPException(status_code=400, detail="There's no quotation to negotiate yet.")
        total_qty = sum(it.quantity for it in top.items) or 1
        per_piece_target = float(data.target_price) / total_qty
        per_piece_original = float(top.total_amount) / total_qty
        gst_pct = 18.0 if top.currency == "INR" else None
        negotiation_targets = [{
            "supplier_id": top.supplier_id,
            "supplier_name": top.supplier.name if top.supplier else "Supplier",
            "original_price": float(top.total_amount),
            "target_price": float(data.target_price),
            "currency": top.currency,
            "quantity": total_qty,
            "gst_percent": gst_pct,
        }]
        decision_label = (
            f"Negotiate — counter-offer {top.currency} {per_piece_target:,.2f}/pc "
            f"(total {top.currency} {float(data.target_price):,.0f}) to "
            f"{negotiation_targets[0]['supplier_name']} "
            f"— they quoted {top.currency} {per_piece_original:,.2f}/pc"
        )

    user_msg = ConversationMessage(
        id=generate_uuid(),
        session_id=session_id,
        role="user",
        content=f"Decision: {decision_label}",
        message_type="text",
    )
    db.add(user_msg)

    if data.decision == "cancel":
        session.status = "cancelled"
        cancel_msg = ConversationMessage(
            id=generate_uuid(),
            session_id=session_id,
            role="assistant",
            content="This RFQ has been cancelled as requested.",
            message_type="text",
            metadata_json={"current_step": "user_decision_gate"},
        )
        db.add(cancel_msg)
        await db.commit()

        from app.workflows.session_workflow import session_workflow_service
        background_tasks.add_task(
            session_workflow_service.submit_decision,
            session_id, thread_id, data.decision, negotiation_targets, data.quotation_id,
        )

        return {
            "message": "RFQ cancelled.",
            "session": _session_detail(session),
            "current_step": session.current_step,
            "error": None,
        }

    session.status = "active"
    await db.flush()

    from app.workflows.session_workflow import session_workflow_service
    background_tasks.add_task(
        session_workflow_service.submit_decision, session_id, thread_id, data.decision, negotiation_targets
    )

    return {
        "message": "Decision received — processing...",
        "session": _session_detail(session),
        "current_step": session.current_step,
        "error": None,
    }


@router.post("/{session_id}/rename")
async def rename_session(
    session_id: str,
    data: RenameSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Rename a session."""
    session = await _get_session_or_404(db, session_id, current_user.id)
    session.title = data.title
    await db.flush()
    return {"id": session.id, "title": session.title}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a session (soft: marks as cancelled)."""
    session = await _get_session_or_404(db, session_id, current_user.id)
    session.status = "cancelled"
    await db.flush()
    return {"id": session.id, "status": "cancelled"}


# ─────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────

async def _get_session_or_404(db: AsyncSession, session_id: str, user_id: str) -> WorkflowSession:
    result = await db.execute(
        select(WorkflowSession).where(
            WorkflowSession.id == session_id,
            WorkflowSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("WorkflowSession", session_id)
    return session


def _session_summary(s: WorkflowSession) -> dict:
    status_emoji = {
        "active": "🔵",
        "waiting": "🟡",
        "completed": "✅",
        "failed": "🔴",
        "cancelled": "⚫",
    }
    return {
        "id": s.id,
        "title": s.title,
        "status": s.status,
        "status_emoji": status_emoji.get(s.status, "⚪"),
        "current_step": s.current_step,
        "current_agent": s.current_agent,
        "progress_percentage": s.progress_percentage,
        "rfq_id": s.rfq_id,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _session_detail(s: WorkflowSession) -> dict:
    return {
        **_session_summary(s),
        "current_node": s.current_node,
        "langgraph_thread_id": s.langgraph_thread_id,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
    }


def _quotation_data(q) -> dict:
    analysis = q.ai_analysis_json or {}
    return {
        "id": q.id,
        "supplier_id": q.supplier_id,
        "supplier_name": q.supplier.name if q.supplier else "Unknown",
        "total_amount": float(q.total_amount),
        "tax_percent": float(q.tax_percent) if q.tax_percent else None,
        "tax_amount": float(q.tax_amount) if q.tax_amount else None,
        "grand_total": float(q.grand_total) if q.grand_total else None,
        "currency": q.currency,
        "delivery_days": q.delivery_days,
        "warranty_terms": q.warranty_terms,
        "payment_terms": q.payment_terms,
        "validity_days": q.validity_days,
        "ai_ranking": q.ai_ranking,
        "is_recommended": q.ai_ranking == 1,
        "negotiation_round": q.negotiation_round or 0,
        "strengths": analysis.get("strengths", []),
        "weaknesses": analysis.get("weaknesses", []),
        "status": q.status,
        "items": [
            {
                "product_name": item.product_name,
                "unit_price": float(item.unit_price),
                "quantity": item.quantity,
                "total_price": float(item.total_price),
            }
            for item in q.items
        ],
    }


def _step_data(s: WorkflowStep) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "display_name": s.display_name,
        "status": s.status,
        "agent": s.agent,
        "order_index": s.order_index,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        "execution_time_ms": s.execution_time_ms,
        "error_message": s.error_message,
    }
