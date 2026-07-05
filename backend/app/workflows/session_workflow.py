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

logger = logging.getLogger(__name__)

STEP_PROGRESS_MAP = {
    "parse_user_request": 7,
    "validate_rfq_data": 14,
    "create_rfq_record": 21,
    "resolve_direct_supplier": 21,
    "select_vendors": 28,
    "generate_rfq_emails": 35,
    "send_rfq_emails": 42,
    "await_supplier_replies": 50,
    "process_attachments": 57,
    "analyze_quotations": 64,
    "present_recommendation": 71,
    "user_decision_gate": 78,
    "negotiate_with_suppliers": 85,
    "generate_purchase_order": 92,
    "send_po_email": 100,
}

STEP_AGENT_MAP = {
    "parse_user_request": "Parser Agent",
    "validate_rfq_data": "Validator Agent",
    "create_rfq_record": "RFQ Agent",
    "resolve_direct_supplier": "Vendor Agent",
    "select_vendors": "Vendor Agent",
    "generate_rfq_emails": "Email Agent",
    "send_rfq_emails": "Email Agent",
    "await_supplier_replies": "Inbox Agent",
    "process_attachments": "OCR Agent",
    "analyze_quotations": "Analysis Agent",
    "present_recommendation": "Analysis Agent",
    "user_decision_gate": "Human",
    "negotiate_with_suppliers": "Negotiation Agent",
    "generate_purchase_order": "PO Agent",
    "send_po_email": "Email Agent",
}

# Short, human-readable "step done" messages posted into the chat as each node
# completes. Steps in RICH_MESSAGE_STEPS instead use _format_response() (which
# produces the fuller supplier list / recommendation / completion text).
NODE_PROGRESS_MESSAGES = {
    "parse_user_request": "📋 Understood your requirement — extracting the details.",
    "validate_rfq_data": "✅ Validated the request details.",
    "create_rfq_record": "📝 Created the RFQ record.",
    "resolve_direct_supplier": "🎯 Located the supplier you specified.",
    "generate_rfq_emails": "✍️ Drafted the RFQ emails.",
    "send_rfq_emails": "📧 Sent the RFQ emails to the suppliers.",
    "process_attachments": "🔎 Extracted the quotation details from the attachment (OCR).",
    "analyze_quotations": "📊 Scored and ranked the quotations.",
    "negotiate_with_suppliers": "🤝 Sent counter-offers to the supplier(s).",
    "generate_purchase_order": "📄 Generated the purchase order document (PDF).",
}

RICH_MESSAGE_STEPS = {"await_supplier_replies", "present_recommendation", "send_po_email"}
WAITING_STEPS = ("await_supplier_replies", "present_recommendation", "user_decision_gate")


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

        workflow_logger.info(f"[SESSION-MODE] {'NEW' if is_new else 'RESUME'} | Thread: {thread_id}")
        config = {"configurable": {"thread_id": thread_id}}

        if is_new:
            stream_input = _initial_state(user_id, thread_id, user_input)
        else:
            snapshot = await graph.aget_state(config)
            current_state = snapshot.values if snapshot else {}
            if not current_state:
                await self._persist_failure(
                    session_id,
                    "This session's workflow state was lost (e.g. the backend restarted "
                    "while it was waiting) and cannot be resumed. Please start a new procurement.",
                )
                return {"current_step": None, "error": "state lost"}

            await graph.aupdate_state(
                config,
                {
                    "user_input": user_input,
                    "received_emails": current_state.get("received_emails", []) + [user_input],
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
        config = {"configurable": {"thread_id": thread_id}}
        acc: dict = {}

        try:
            async for chunk in graph.astream(stream_input, config=config, stream_mode="updates"):
                if not isinstance(chunk, dict):
                    continue
                for node, delta in chunk.items():
                    # `__interrupt__` (and any non-dict payload) is a control signal, not a node result.
                    if node == "__interrupt__" or not isinstance(delta, dict):
                        continue
                    acc.update(delta)
                    step = delta.get("current_step") or node
                    workflow_logger.info(f"[NODE-DONE] {session_id} -> {step}")
                    await self._persist_node_progress(session_id, step, acc)
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

                session.current_step = step
                session.current_node = step
                session.current_agent = STEP_AGENT_MAP.get(step, session.current_agent)
                session.progress_percentage = STEP_PROGRESS_MAP.get(step, session.progress_percentage)

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

                await self._update_steps(db, session_id, step)
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

                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error(f"[SESSION-WORKFLOW] Failed to persist node '{step}' for {session_id}: {e}", exc_info=True)

    async def _persist_terminal(self, session_id: str, values: dict):
        """Correct the session's terminal status/message once the graph has actually ended."""
        decision = values.get("user_decision")
        # Only cancel needs special handling here — approve ends on send_po_email (already
        # marked completed + messaged during streaming), and negotiate loops back to a
        # waiting step rather than ending.
        if decision != "cancel":
            return

        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(WorkflowSession).where(WorkflowSession.id == session_id))
                session = result.scalar_one_or_none()
                if session is None:
                    return

                session.status = "cancelled"
                # Mark the decision gate itself completed so the tree doesn't sit "running".
                from app.models.base import ist_now
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

                db.add(ConversationMessage(
                    id=generate_uuid(),
                    session_id=session_id,
                    role="assistant",
                    content="This RFQ has been cancelled as requested.",
                    message_type="text",
                    metadata_json={"current_step": "user_decision_gate"},
                ))
                await db.commit()
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
                db.add(ConversationMessage(
                    id=generate_uuid(),
                    session_id=session_id,
                    role="assistant",
                    content=f"Something went wrong: {error}",
                    message_type="text",
                    metadata_json={"current_step": "failed"},
                ))
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error(f"[SESSION-WORKFLOW] Failed to persist failure for {session_id}: {e}", exc_info=True)

    # ─────────────────────────────────────────────────────────────
    # Persistence helpers
    # ─────────────────────────────────────────────────────────────

    async def _update_steps(self, db: AsyncSession, session_id: str, current_step: str):
        """Mark steps before `current_step` completed and `current_step` running."""
        from app.models.base import ist_now

        result = await db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.session_id == session_id)
            .order_by(WorkflowStep.order_index)
        )
        steps = list(result.scalars().all())

        current_found = False
        for step in steps:
            if step.name == current_step:
                if step.status != "completed":
                    step.status = "running"
                    step.started_at = step.started_at or ist_now()
                step.agent = STEP_AGENT_MAP.get(step.name, step.agent)
                current_found = True
            elif not current_found:
                if step.status != "completed":
                    step.status = "completed"
                    step.completed_at = step.completed_at or ist_now()
                    if step.started_at:
                        # MySQL DATETIME columns drop tzinfo on round-trip, so a value just
                        # read back (naive) can collide with a fresh ist_now() (aware) and
                        # raise TypeError. Normalize both to naive before subtracting.
                        completed_at = step.completed_at.replace(tzinfo=None)
                        started_at = step.started_at.replace(tzinfo=None)
                        step.execution_time_ms = (completed_at - started_at).total_seconds() * 1000
            # Steps after current remain pending.

    async def _emit_event(
        self, db: AsyncSession, session_id: str, current_step: str, parsed: dict, suppliers: list
    ):
        """Emit a timeline event for the current step."""
        event_titles = {
            "parse_user_request": "Requirement Received",
            "validate_rfq_data": "RFQ Data Validated",
            "create_rfq_record": "RFQ Created",
            "resolve_direct_supplier": "Direct Supplier Resolved",
            "select_vendors": f"Vendors Selected ({len(suppliers)} found)",
            "generate_rfq_emails": "RFQ Emails Generated",
            "send_rfq_emails": "Emails Sent to Suppliers",
            "await_supplier_replies": "Waiting for Supplier Responses",
            "process_attachments": "Processing Quotation Documents",
            "analyze_quotations": "Quotation Analysis Complete",
            "present_recommendation": "AI Recommendation Ready",
            "user_decision_gate": "Awaiting Your Decision",
            "negotiate_with_suppliers": "Negotiation Started",
            "generate_purchase_order": "Purchase Order Generated",
            "send_po_email": "Purchase Order Sent",
        }

        title = event_titles.get(current_step, f"Step: {current_step}")
        agent = STEP_AGENT_MAP.get(current_step, "System")

        db.add(WorkflowEvent(
            id=generate_uuid(),
            session_id=session_id,
            event_type="step_completed",
            title=title,
            description=parsed.get("title", ""),
            agent=agent,
            metadata_json={"step": current_step, "suppliers_count": len(suppliers)},
        ))

    def _node_message(self, step: str, values: dict) -> str | None:
        """The chat line to post for a just-completed node (None = post nothing)."""
        parsed = values.get("parsed_intent") or {}

        # Incomplete request: surface the clarification exactly once, at the validate node
        # (the terminating node on that path), and stay silent on parse.
        if parsed and not parsed.get("is_complete"):
            if step == "validate_rfq_data":
                return parsed.get(
                    "clarification_needed",
                    "Could you tell me a bit more about what you'd like to procure?",
                )
            return None

        if step == "select_vendors":
            suppliers = values.get("selected_suppliers", [])
            if not suppliers:
                return "🔍 No matching suppliers were found in the catalog for this request."
            names = ", ".join(s.get("name", "?") for s in suppliers[:5])
            return f"🔍 Found {len(suppliers)} matching supplier(s): {names}."

        if step in RICH_MESSAGE_STEPS:
            return self._format_response({**values, "current_step": step})

        return NODE_PROGRESS_MESSAGES.get(step)

    def _format_response(self, result: dict) -> str:
        """Format a graph state into the fuller user-facing message for a waiting/terminal step."""
        if result.get("error"):
            return f"Something went wrong: {result['error']}"

        current_step = result.get("current_step", "")
        parsed = result.get("parsed_intent", {})
        suppliers = result.get("selected_suppliers", [])

        if not parsed.get("is_complete"):
            return parsed.get("clarification_needed", "Could you tell me more about what you need?")

        if current_step == "present_recommendation":
            rec = result.get("ai_recommendation", {})
            top = (result.get("rankings") or [{}])[0]
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
