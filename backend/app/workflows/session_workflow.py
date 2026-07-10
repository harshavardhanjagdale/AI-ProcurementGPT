"""
Session Workflow Service - Bridges WorkflowSession entities with the LangGraph orchestrator.

Drives the compiled procurement graph with `astream` (rather than `ainvoke`) so that
every node's completion is persisted to the DB *as it happens* — the workspace UI polls
session/steps/chat/events every few seconds, so streaming + per-node commits is what makes
the workflow tree light up node-by-node and a running commentary appear in the chat,
instead of the UI jumping straight to the first interrupt.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import get_procurement_graph
from app.database.connection import AsyncSessionLocal
from app.models.workflow_session import WorkflowSession
from app.models.workflow_step import WorkflowStep
from app.models.workflow_event import WorkflowEvent
from app.models.conversation_message import ConversationMessage
from app.models.base import generate_uuid
from app.agents.state import ProcurementState
from app.workflows.workflow_logger import workflow_logger
from app.workflows.event_bus import workflow_event_bus
from app.models.base import ist_now
from app.ai.token_tracker import track_usage, get_current_usage

logger = logging.getLogger(__name__)

STEP_PROGRESS_MAP = {
    "parse_request": 8,
    "create_rfq_record": 16,
    "resolve_direct_supplier": 16,
    "select_vendors": 25,
    "generate_rfq_emails": 33,
    "send_rfq_emails": 42,
    "await_supplier_replies": 50,
    "ocr_extract": 66,
    "user_decision_gate": 75,
    "negotiate_with_suppliers": 83,
    "generate_purchase_order": 92,
    "send_po_email": 100,
}

STEP_AGENT_MAP = {
    "parse_request": "Parser Agent",
    "create_rfq_record": "RFQ Agent",
    "resolve_direct_supplier": "Vendor Agent",
    "select_vendors": "Vendor Agent",
    "generate_rfq_emails": "Email Agent",
    "send_rfq_emails": "Email Agent",
    "await_supplier_replies": "Inbox Agent",
    "ocr_extract": "OCR Agent",
    "user_decision_gate": "Human",
    "negotiate_with_suppliers": "Negotiation Agent",
    "generate_purchase_order": "PO Agent",
    "send_po_email": "Email Agent",
}

# Short, human-readable "step done" messages posted into the chat as each node
# completes. Steps in RICH_MESSAGE_STEPS instead use _format_response() (which
# produces the fuller supplier list / recommendation / completion text).
NODE_PROGRESS_MESSAGES = {
    "parse_request": "📋 Understood and validated your requirement.",
    "generate_rfq_emails": "✍️ Drafted the RFQ emails.",
    "send_rfq_emails": "📧 Sent the RFQ emails to the suppliers.",
    "negotiate_with_suppliers": "🤝 Sent counter-offers to the supplier(s).",
    "generate_purchase_order": "📄 Generated the purchase order document (PDF).",
}

STEP_PROGRESS_ORDER = {step: idx for idx, step in enumerate(STEP_PROGRESS_MAP)}

STEP_PHASE_MAP = {
    "parse_request": "Intake",
    "create_rfq_record": "Intake",
    "resolve_direct_supplier": "Sourcing",
    "select_vendors": "Sourcing",
    "generate_rfq_emails": "Outreach",
    "send_rfq_emails": "Outreach",
    "await_supplier_replies": "Waiting",
    "ocr_extract": "Evaluation",
    "user_decision_gate": "Decision",
    "negotiate_with_suppliers": "Negotiation",
    "generate_purchase_order": "Finalizing",
    "send_po_email": "Finalizing",
}

RICH_MESSAGE_STEPS = {"await_supplier_replies", "ocr_extract", "send_po_email"}
WAITING_STEPS = ("await_supplier_replies", "ocr_extract", "user_decision_gate")


def _initial_state(user_id: str, thread_id: str, user_input: str) -> ProcurementState:
    return {
        "rfq_id": "",
        "user_id": user_id,
        "workflow_run_id": thread_id,
        "user_input": user_input,
        "parsed_intent": {},
        "selected_suppliers": [],
        "supplier_scores": [],
        "rfq_email_drafts": [],
        "rfq_emails_sent": False,
        "received_emails": [],
        "ocr_results": [],
        "quotations": [],
        "comparison_matrix": {},
        "ai_recommendation": {},
        "rankings": [],
        "user_decision": None,
        "negotiation_targets": [],
        "negotiation_round": 0,
        "negotiation_emails_sent": False,
        "negotiation_results": [],
        "po_generated": False,
        "po_pdf_path": None,
        "po_email_sent": False,
        "current_step": "start",
        "error": None,
        "messages": [],
    }


class SessionWorkflowService:
    """Manages workflow execution within a session context, streaming live progress."""

    async def run_workflow(self, session_id: str, user_input: str, user_id: str) -> dict:
        """
        Start (or continue) a session's workflow, streaming node-by-node progress to the DB.

        Manages its own DB sessions so it can safely run as a fire-and-forget background
        task (the request that dispatched it has long since returned and closed its session).
        """
        workflow_logger.info(f"\n[RUN-WORKFLOW-START] Session: {session_id}")
        workflow_logger.info(f"[USER-INPUT] {user_input[:100]}...")

        graph = get_procurement_graph()

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(WorkflowSession).where(WorkflowSession.id == session_id))
            session = result.scalar_one_or_none()
            if not session:
                workflow_logger.error(f"[ERROR] Session not found: {session_id}")
                return {"error": "Session not found", "current_step": None}

            thread_id = session.langgraph_thread_id
            is_new = thread_id is None
            if is_new:
                thread_id = generate_uuid()
                session.langgraph_thread_id = thread_id
                await db.commit()

        config = {"configurable": {"thread_id": thread_id}}

        # Decide whether this message resumes an in-flight graph or starts a fresh run.
        # A graph that has TERMINATED (snapshot.next is empty) — because the request was
        # incomplete, no suppliers matched, it was cancelled, or a PO already completed —
        # cannot be "resumed": invoking it does nothing. In that case the user's new
        # message is a fresh requirement, so we re-run from parse_request on a new thread
        # and reset the step tracker. Only a graph parked at a real interrupt
        # (await_supplier_replies / user_decision_gate → next is non-empty) is resumed.
        restart = False
        if not is_new:
            snapshot = await graph.aget_state(config)
            if snapshot is None or not snapshot.values:
                restart = True  # checkpoint lost (e.g. restart) → just start over cleanly
            elif not snapshot.next:
                restart = True  # graph ended (dead-end or completed) → treat as new request

        if is_new or restart:
            if restart:
                thread_id = generate_uuid()
                config = {"configurable": {"thread_id": thread_id}}
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(WorkflowSession).where(WorkflowSession.id == session_id))
                    s = result.scalar_one_or_none()
                    if s is not None:
                        s.langgraph_thread_id = thread_id
                        s.rfq_id = None  # a fresh run creates a fresh RFQ
                        await self._reset_steps(db, session_id)
                        await db.commit()
            workflow_logger.info(f"[SESSION-MODE] {'RESTART' if restart else 'NEW'} | Thread: {thread_id}")
            stream_input = _initial_state(user_id, thread_id, user_input)
        else:
            workflow_logger.info(f"[SESSION-MODE] RESUME | Thread: {thread_id}")
            await graph.aupdate_state(
                config,
                {
                    "user_input": user_input,
                    "received_emails": snapshot.values.get("received_emails", []) + [user_input],
                },
            )
            stream_input = None

        return await self._run_graph_streaming(session_id, thread_id, stream_input)

    async def resume_after_reply(self, session_id: str, thread_id: str) -> dict:
        """
        Resume a session parked at await_supplier_replies after a supplier email arrived
        (IMAP polling / webhook / manual check), streaming OCR → analysis → recommendation live.
        """
        graph = get_procurement_graph()
        config = {"configurable": {"thread_id": thread_id}}

        snapshot = await graph.aget_state(config)
        if not snapshot or not snapshot.values:
            await self._persist_failure(
                session_id,
                "This session's workflow state was lost and cannot be resumed.",
            )
            return {"current_step": None, "error": "state lost"}

        return await self._run_graph_streaming(session_id, thread_id, None)

    async def submit_decision(
        self,
        session_id: str,
        thread_id: str,
        decision: str,
        negotiation_targets: list[dict] | None = None,
    ) -> dict:
        """
        Apply the user's approve/negotiate/cancel decision and stream the resulting run
        (PO generation + send for approve; counter-offers for negotiate) live to the UI.
        """
        graph = get_procurement_graph()
        config = {"configurable": {"thread_id": thread_id}}

        snapshot = await graph.aget_state(config)
        if not snapshot or not snapshot.values:
            await self._persist_failure(
                session_id,
                "This session's workflow state was lost and cannot be resumed.",
            )
            return {"current_step": None, "error": "state lost"}

        # Clear any stale error so it doesn't keep poisoning status on every future resume.
        state_update: dict = {"user_decision": decision, "error": None}
        if negotiation_targets:
            state_update["negotiation_targets"] = negotiation_targets
        await graph.aupdate_state(config, state_update)

        return await self._run_graph_streaming(session_id, thread_id, None)

    # ─────────────────────────────────────────────────────────────
    # Streaming core
    # ─────────────────────────────────────────────────────────────

    async def _run_graph_streaming(self, session_id: str, thread_id: str, stream_input) -> dict:
        """Stream the graph, persisting each node's completion (step + event + chat) as it lands."""
        graph = get_procurement_graph()
        config = {
            "configurable": {"thread_id": thread_id},
            "run_name": f"procurement-{session_id[:8]}",
            "metadata": {"session_id": session_id, "thread_id": thread_id},
            "tags": ["procurement", f"session:{session_id[:8]}"],
        }

        # Seed the accumulator with the full existing checkpoint state so that on a RESUME
        # (e.g. ocr_extract / decision runs, which only emit their own node's deltas) the
        # per-node message/status logic can still see earlier fields like parsed_intent.
        # Without this, _format_response's is_complete guard wrongly falls through to the
        # "tell me more" clarification even though the request was fully parsed earlier.
        acc: dict = {}
        try:
            existing = await graph.aget_state(config)
            if existing and existing.values:
                acc.update(existing.values)
        except Exception:
            pass

        # Attribute every LLM call the graph nodes make during this run to this
        # thread, so we can report tokens + cost per procurement (see token_tracker).
        try:
            with track_usage(thread_id) as usage:
                async for chunk in graph.astream(stream_input, config=config, stream_mode="updates"):
                    if not isinstance(chunk, dict):
                        continue
                    for node, delta in chunk.items():
                        # `__interrupt__` (and any non-dict payload) is a control signal, not a node result.
                        if node == "__interrupt__" or not isinstance(delta, dict):
                            continue
                        acc.update(delta)
                        step = delta.get("current_step") or node
                        workflow_logger.info(
                            f"[NODE-DONE] {session_id} -> {step} "
                            f"| tokens so far: {usage.total_tokens} (~${usage.cost_usd:.4f})"
                        )
                        await self._persist_node_progress(session_id, step, acc)
                workflow_logger.info(f"[TOKEN-USAGE] {session_id} -> {usage.summary()}")
        except Exception as e:
            logger.error(f"[SESSION-WORKFLOW] Streaming failed for session {session_id}: {e}", exc_info=True)
            await self._persist_failure(session_id, str(e))
            return {"current_step": acc.get("current_step"), "error": str(e)}

        # Reconcile against the authoritative checkpoint: fix terminal status (completed/
        # cancelled) that a per-node update can't know about (e.g. the graph ending right
        # after user_decision_gate on a cancel).
        snapshot = await graph.aget_state(config)
        final = snapshot.values if (snapshot and snapshot.values) else acc
        is_terminal = snapshot is not None and not snapshot.next
        if is_terminal:
            await self._persist_terminal(session_id, final)

        return {
            "current_step": final.get("current_step"),
            "error": final.get("error"),
            "rfq_id": final.get("rfq_id"),
            "parsed_intent": final.get("parsed_intent", {}),
            "selected_suppliers": final.get("selected_suppliers", []),
        }

    async def _persist_node_progress(self, session_id: str, step: str, values: dict):
        """Commit a single node's completion so polling picks it up immediately."""
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(WorkflowSession).where(WorkflowSession.id == session_id))
                session = result.scalar_one_or_none()
                if session is None:
                    return

                parsed = values.get("parsed_intent") or {}

                # After ocr_extract the graph pauses *before* user_decision_gate, so surface
                # the decision gate as the active step (not a completed one) — that's the
                # step actually awaiting the user.
                # If no quotations were found, the graph will route back to waiting — show
                # await_supplier_replies as the current step, not ocr_extract (which triggers
                # the decision buttons).
                display_step = step
                if step == "ocr_extract" and values.get("no_quotations_yet"):
                    display_step = "await_supplier_replies"
                elif step == "ocr_extract" and values.get("rankings"):
                    display_step = "user_decision_gate"

                session.current_step = display_step
                session.current_node = display_step
                session.current_agent = STEP_AGENT_MAP.get(display_step, session.current_agent)
                session.progress_percentage = STEP_PROGRESS_MAP.get(display_step, session.progress_percentage)

                # Sync the RFQ id onto the session row as soon as create_rfq_record produces
                # it. This is what links a later supplier reply back to this session — the
                # email worker matches replies via WorkflowSession.rfq_id, so if it stays
                # NULL the reply can never resume the graph and OCR never runs.
                rfq_id = values.get("rfq_id")
                if rfq_id and not session.rfq_id:
                    session.rfq_id = rfq_id

                if values.get("error"):
                    session.status = "failed"
                elif step in WAITING_STEPS:
                    session.status = "waiting"
                elif step == "send_po_email" and values.get("po_email_sent"):
                    session.status = "completed"
                else:
                    session.status = "active"

                # Auto-title from the parsed intent on the first substantive node.
                if session.title in (None, "", "New Procurement") and parsed.get("title"):
                    session.title = parsed["title"][:100]

                await self._update_steps(db, session_id, step, values)
                await self._emit_event(db, session_id, step, parsed, values.get("selected_suppliers", []))

                content = self._node_message(step, values)
                if content:
                    db.add(ConversationMessage(
                        id=generate_uuid(),
                        session_id=session_id,
                        role="assistant",
                        content=content,
                        message_type="text",
                        metadata_json={"current_step": step},
                    ))

                # Capture values for WS event BEFORE commit (avoids expired-session reads)
                ws_progress = session.progress_percentage
                ws_agent = session.current_agent
                ws_status = session.status
                ws_title = session.title

                all_steps = await db.execute(
                    select(WorkflowStep)
                    .where(WorkflowStep.session_id == session_id)
                    .order_by(WorkflowStep.order_index)
                )
                ws_steps = [self._step_to_dict(s) for s in all_steps.scalars().all()]

                await db.commit()

                # Publish real-time event to WebSocket subscribers
                chat_msg = None
                if content:
                    chat_msg = {
                        "id": generate_uuid(),
                        "role": "assistant",
                        "content": content,
                        "message_type": "text",
                        "created_at": ist_now().isoformat(),
                    }

                await workflow_event_bus.publish(session_id, {
                    "type": "workflow_progress",
                    "workflowId": session_id,
                    "currentStep": display_step,
                    "stepIndex": STEP_PROGRESS_ORDER.get(display_step, 0),
                    "totalSteps": len(STEP_PROGRESS_MAP),
                    "progress": ws_progress,
                    "currentStage": STEP_PHASE_MAP.get(display_step, ""),
                    "currentAgent": ws_agent,
                    "status": ws_status,
                    "title": ws_title,
                    "message": content,
                    "timestamp": ist_now().isoformat(),
                    "steps": ws_steps,
                    "chatMessage": chat_msg,
                })

            except Exception as e:
                await db.rollback()
                logger.error(f"[SESSION-WORKFLOW] Failed to persist node '{step}' for {session_id}: {e}", exc_info=True)

    async def _persist_terminal(self, session_id: str, values: dict):
        """Correct the session's terminal status/message once the graph has actually ended."""
        decision = values.get("user_decision")
        step = values.get("current_step")
        parsed = values.get("parsed_intent") or {}

        # A "dead end" is a graph that ended because it needs a fresh requirement, not
        # because the procurement succeeded: no suppliers matched, or the request was
        # never complete. Reopen the session for input so the user can restate it — the
        # next message will restart the workflow from scratch (see run_workflow).
        no_suppliers = (
            (step == "select_vendors" and not values.get("selected_suppliers"))
            or (step == "resolve_direct_supplier" and not values.get("selected_suppliers"))
        )
        incomplete = bool(parsed) and not parsed.get("is_complete")
        dead_end = no_suppliers or incomplete

        # Only cancel / dead-ends need fix-up here — approve ends on send_po_email (already
        # marked completed + messaged during streaming), and negotiate loops back to a
        # waiting step rather than ending.
        if decision != "cancel" and not dead_end:
            return

        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(WorkflowSession).where(WorkflowSession.id == session_id))
                session = result.scalar_one_or_none()
                if session is None:
                    return

                if dead_end and decision != "cancel":
                    session.status = "active"
                    session.current_step = "waiting_input"
                    session.current_node = "waiting_input"
                    dead_end_msg = None
                    if no_suppliers:
                        if step == "resolve_direct_supplier":
                            supplier_name = parsed.get("direct_supplier", "the specified supplier")
                            dead_end_msg = f"'{supplier_name}' is not in our supplier database. Please try a different supplier name or a general product request so I can find matching vendors."
                        else:
                            dead_end_msg = "I couldn't find any suppliers for that. Please restate what you'd like to procure (try different wording or a broader category) and I'll start again."
                        db.add(ConversationMessage(
                            id=generate_uuid(),
                            session_id=session_id,
                            role="assistant",
                            content=dead_end_msg,
                            message_type="text",
                            metadata_json={"current_step": "waiting_input"},
                        ))
                    await db.commit()

                    await workflow_event_bus.publish(session_id, {
                        "type": "workflow_progress",
                        "workflowId": session_id,
                        "currentStep": "waiting_input",
                        "totalSteps": len(STEP_PROGRESS_MAP),
                        "progress": session.progress_percentage,
                        "currentAgent": session.current_agent,
                        "status": "active",
                        "title": session.title,
                        "message": dead_end_msg,
                        "timestamp": ist_now().isoformat(),
                        "chatMessage": {
                            "id": generate_uuid(),
                            "role": "assistant",
                            "content": dead_end_msg,
                            "message_type": "text",
                            "created_at": ist_now().isoformat(),
                        } if dead_end_msg else None,
                    })
                    return

                session.status = "cancelled"
                await self._update_steps(db, session_id, "user_decision_gate")
                gate = (await db.execute(
                    select(WorkflowStep).where(
                        WorkflowStep.session_id == session_id,
                        WorkflowStep.name == "user_decision_gate",
                    )
                )).scalar_one_or_none()
                if gate:
                    gate.status = "completed"
                    gate.completed_at = gate.completed_at or ist_now()

                cancel_msg = "This RFQ has been cancelled as requested."
                db.add(ConversationMessage(
                    id=generate_uuid(),
                    session_id=session_id,
                    role="assistant",
                    content=cancel_msg,
                    message_type="text",
                    metadata_json={"current_step": "user_decision_gate"},
                ))
                await db.commit()

                all_steps = await db.execute(
                    select(WorkflowStep)
                    .where(WorkflowStep.session_id == session_id)
                    .order_by(WorkflowStep.order_index)
                )
                step_list = list(all_steps.scalars().all())
                await workflow_event_bus.publish(session_id, {
                    "type": "workflow_complete",
                    "workflowId": session_id,
                    "currentStep": "user_decision_gate",
                    "totalSteps": len(STEP_PROGRESS_MAP),
                    "progress": session.progress_percentage,
                    "currentAgent": "Human",
                    "status": "cancelled",
                    "title": session.title,
                    "message": cancel_msg,
                    "timestamp": ist_now().isoformat(),
                    "steps": [self._step_to_dict(s) for s in step_list],
                    "chatMessage": {
                        "id": generate_uuid(),
                        "role": "assistant",
                        "content": cancel_msg,
                        "message_type": "text",
                        "created_at": ist_now().isoformat(),
                    },
                })

            except Exception as e:
                await db.rollback()
                logger.error(f"[SESSION-WORKFLOW] Failed terminal persist for {session_id}: {e}", exc_info=True)

    async def _persist_failure(self, session_id: str, error: str):
        """Mark the session failed and surface the error in the chat + timeline."""
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(WorkflowSession).where(WorkflowSession.id == session_id))
                session = result.scalar_one_or_none()
                if session is not None:
                    session.status = "failed"

                db.add(WorkflowEvent(
                    id=generate_uuid(),
                    session_id=session_id,
                    event_type="error",
                    title="Workflow Error",
                    description=error,
                    agent="System",
                ))
                error_msg = f"Something went wrong: {error}"
                db.add(ConversationMessage(
                    id=generate_uuid(),
                    session_id=session_id,
                    role="assistant",
                    content=error_msg,
                    message_type="text",
                    metadata_json={"current_step": "failed"},
                ))
                await db.commit()

                await workflow_event_bus.publish(session_id, {
                    "type": "workflow_error",
                    "workflowId": session_id,
                    "currentStep": session.current_step if session else None,
                    "totalSteps": len(STEP_PROGRESS_MAP),
                    "progress": session.progress_percentage if session else 0,
                    "currentAgent": session.current_agent if session else None,
                    "status": "failed",
                    "title": session.title if session else None,
                    "message": error_msg,
                    "timestamp": ist_now().isoformat(),
                    "chatMessage": {
                        "id": generate_uuid(),
                        "role": "assistant",
                        "content": error_msg,
                        "message_type": "text",
                        "created_at": ist_now().isoformat(),
                    },
                })

            except Exception as e:
                await db.rollback()
                logger.error(f"[SESSION-WORKFLOW] Failed to persist failure for {session_id}: {e}", exc_info=True)

    # ─────────────────────────────────────────────────────────────
    # Persistence helpers
    # ─────────────────────────────────────────────────────────────

    async def _reset_steps(self, db: AsyncSession, session_id: str):
        """Reset every step back to pending — used when a session restarts a fresh run."""
        result = await db.execute(select(WorkflowStep).where(WorkflowStep.session_id == session_id))
        for step in result.scalars().all():
            step.status = "pending"
            step.started_at = None
            step.completed_at = None
            step.execution_time_ms = None

    # Canonical order of the graph's steps (for deciding what "before" means).
    _MAIN_ORDER = [
        "parse_request", "create_rfq_record", "resolve_direct_supplier", "select_vendors",
        "generate_rfq_emails", "send_rfq_emails", "await_supplier_replies", "ocr_extract",
        "user_decision_gate", "negotiate_with_suppliers", "generate_purchase_order", "send_po_email",
    ]

    async def _update_steps(self, db: AsyncSession, session_id: str, ran_step: str, values: dict | None = None):
        """
        Reflect the step tracker after node `ran_step` actually executed.

        Only steps that genuinely ran are marked completed — conditionally-skipped branch
        nodes (resolve_direct_supplier when there's no direct supplier; negotiate when no
        negotiation happened) are left pending, never falsely green. Waiting/approval steps
        (await_supplier_replies, and the decision gate after ocr_extract) are shown as
        *running* (active), not completed.
        """
        values = values or {}
        parsed = values.get("parsed_intent") or {}
        skip: set[str] = set()
        if not parsed.get("direct_supplier"):
            skip.add("resolve_direct_supplier")
        if not values.get("negotiation_round"):
            skip.add("negotiate_with_suppliers")

        try:
            ran_idx = self._MAIN_ORDER.index(ran_step)
        except ValueError:
            ran_idx = -1

        # await_supplier_replies is a resting/waiting node; the decision gate becomes active
        # right after ocr_extract. Both should show "running", not "completed".
        waiting_step = None
        if ran_step == "await_supplier_replies":
            waiting_step = "await_supplier_replies"
        elif ran_step == "ocr_extract":
            waiting_step = "user_decision_gate"

        result = await db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.session_id == session_id)
            .order_by(WorkflowStep.order_index)
        )
        steps = list(result.scalars().all())

        def _complete(step):
            step.status = "completed"
            step.completed_at = step.completed_at or ist_now()
            step.started_at = step.started_at or step.completed_at
            if step.started_at and step.completed_at:
                # MySQL DATETIME drops tzinfo on round-trip — normalize before subtracting.
                c = step.completed_at.replace(tzinfo=None)
                s = step.started_at.replace(tzinfo=None)
                step.execution_time_ms = (c - s).total_seconds() * 1000

        # If the current step ended with an error (e.g. supplier not found), mark it failed
        step_has_error = bool(values.get("error")) and ran_step != "await_supplier_replies"

        for step in steps:
            if step.name in skip:
                continue  # branch not taken → leave pending
            idx = self._MAIN_ORDER.index(step.name) if step.name in self._MAIN_ORDER else 999

            if step.name == waiting_step:
                if step.status != "completed":
                    step.status = "running"
                    step.started_at = step.started_at or ist_now()
                    step.agent = STEP_AGENT_MAP.get(step.name, step.agent)
            elif step.name == ran_step:
                if ran_step == "await_supplier_replies":
                    step.status = "running"
                    step.started_at = step.started_at or ist_now()
                elif step_has_error:
                    step.status = "failed"
                    step.started_at = step.started_at or ist_now()
                    step.completed_at = ist_now()
                    step.error_message = values.get("error", "")[:500]
                else:
                    _complete(step)
                step.agent = STEP_AGENT_MAP.get(step.name, step.agent)
            elif idx <= ran_idx and step.status != "completed":
                _complete(step)  # an earlier on-path step that ran
            # steps after the current one stay pending — do NOT mark them
            # steps after the current one stay pending

    async def _emit_event(
        self, db: AsyncSession, session_id: str, current_step: str, parsed: dict, suppliers: list
    ):
        """Emit a timeline event for the current step."""
        event_titles = {
            "parse_request": "Requirement Understood",
            "create_rfq_record": "RFQ Created",
            "resolve_direct_supplier": "Direct Supplier Resolved",
            "select_vendors": f"Vendors Selected ({len(suppliers)} found)",
            "generate_rfq_emails": "RFQ Emails Generated",
            "send_rfq_emails": "Emails Sent to Suppliers",
            "await_supplier_replies": "Waiting for Supplier Responses",
            "ocr_extract": "Quotations Extracted & Analyzed",
            "user_decision_gate": "Awaiting Your Decision",
            "negotiate_with_suppliers": "Negotiation Started",
            "generate_purchase_order": "Purchase Order Generated",
            "send_po_email": "Purchase Order Sent",
        }

        title = event_titles.get(current_step, f"Step: {current_step}")
        agent = STEP_AGENT_MAP.get(current_step, "System")

        # Attach the running token/cost total so the timeline can show live spend.
        usage = get_current_usage()
        event_meta = {"step": current_step, "suppliers_count": len(suppliers)}
        if usage is not None:
            event_meta["tokens"] = usage.summary()

        db.add(WorkflowEvent(
            id=generate_uuid(),
            session_id=session_id,
            event_type="step_completed",
            title=title,
            description=parsed.get("title", ""),
            agent=agent,
            metadata_json=event_meta,
        ))

    def _node_message(self, step: str, values: dict) -> str | None:
        """The chat line to post for a just-completed node (None = post nothing)."""
        parsed = values.get("parsed_intent") or {}

        # Incomplete request: the merged parse_request node is the terminating node on
        # that path, so surface the clarification there.
        if parsed and not parsed.get("is_complete"):
            if step == "parse_request":
                return parsed.get(
                    "clarification_needed",
                    "Could you tell me a bit more about what you'd like to procure?",
                )
            return None

        if step == "resolve_direct_supplier":
            suppliers = values.get("selected_suppliers", [])
            if not suppliers:
                supplier_name = parsed.get("direct_supplier", "the specified supplier")
                return f"⚠️ Could not find '{supplier_name}' in our supplier database. Will search for alternatives."
            return f"🎯 Located the supplier: {suppliers[0].get('name', 'Unknown')}."

        if step == "select_vendors":
            suppliers = values.get("selected_suppliers", [])
            if not suppliers:
                return "🔍 No matching suppliers were found in the catalog for this request."
            names = ", ".join(s.get("name", "?") for s in suppliers[:5])
            return f"🔍 Found {len(suppliers)} matching supplier(s): {names}."

        if step == "ocr_extract" and values.get("no_quotations_yet"):
            return "📩 Received a response from the supplier, but no quotation document was attached. Still waiting for a valid quotation with pricing details..."

        if step in RICH_MESSAGE_STEPS:
            return self._format_response({**values, "current_step": step})

        return NODE_PROGRESS_MESSAGES.get(step)

    @staticmethod
    def _step_to_dict(s: WorkflowStep) -> dict:
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

    def _format_response(self, result: dict) -> str:
        """Format a graph state into the fuller user-facing message for a waiting/terminal step."""
        if result.get("error"):
            return f"Something went wrong: {result['error']}"

        current_step = result.get("current_step", "")
        parsed = result.get("parsed_intent", {})
        suppliers = result.get("selected_suppliers", [])

        if not parsed.get("is_complete"):
            return parsed.get("clarification_needed", "Could you tell me more about what you need?")

        if current_step == "ocr_extract":
            rec = result.get("ai_recommendation", {})
            top = (result.get("rankings") or [{}])[0]
            if not result.get("rankings"):
                return "I've processed the supplier response, but couldn't extract a comparable quotation yet. I'll keep monitoring for valid quotes."
            return (
                f"All quotations have been analyzed! My recommendation: **{rec.get('supplier_name', 'See comparison')}**\n\n"
                f"Score: {top.get('score', 0)}/100\n\n"
                f"Reason: {rec.get('reasoning', 'Best overall value.')}\n\n"
                f"Would you like to **approve**, **negotiate**, or **cancel**?"
            )

        if current_step == "user_decision_gate" and result.get("user_decision") == "cancel":
            return "This RFQ has been cancelled as requested."

        if current_step in ("generate_purchase_order", "send_po_email"):
            if result.get("po_email_sent"):
                return "Purchase order generated and sent to the supplier! This procurement is complete."
            return "Purchase order generated. Sending it to the supplier now..."

        if current_step == "await_supplier_replies":
            if result.get("negotiation_round", 0) > 0:
                return "Counter-offer sent to the supplier! I'm now waiting for their reply."
            return "RFQ emails have been sent! I'm now monitoring for supplier responses. I'll notify you as soon as quotations arrive."

        direct_supplier = parsed.get("direct_supplier")

        if suppliers and direct_supplier:
            s = suppliers[0]
            return (
                f"Got it! I'll purchase **{parsed.get('title')}** directly from **{s['name']}**.\n\n"
                f"I'm generating the RFQ email now and will send it to {s.get('email', 'them')}. "
                f"I'll notify you when they respond."
            )

        if suppliers:
            supplier_list = "\n".join(
                f"  {i+1}. **{s['name']}** ({s.get('country', 'N/A')}) — Rating: {s.get('rating', 0)}/5"
                for i, s in enumerate(suppliers[:5])
            )
            return (
                f"I've understood your request: **{parsed.get('title')}**\n\n"
                f"Found {len(suppliers)} matching suppliers:\n{supplier_list}\n\n"
                f"Generating RFQ emails and sending them now. I'll update you when responses arrive."
            )

        return f"Processing your request... (step: {current_step})"


session_workflow_service = SessionWorkflowService()
