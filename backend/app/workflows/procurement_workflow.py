"""
Procurement Workflow Service - High-level interface for triggering
and managing LangGraph workflow executions with enhanced monitoring.
"""
import logging
import uuid
from datetime import datetime, timezone

from app.agents.orchestrator import get_procurement_graph
from app.agents.state import ProcurementState

logger = logging.getLogger(__name__)


class ProcurementWorkflowService:
    @property
    def graph(self):
        return get_procurement_graph()

    async def start_workflow(
        self,
        user_input: str,
        user_id: str,
        rfq_id: str | None = None,
    ) -> dict:
        """
        Start a new procurement workflow from user's natural language input.

        Returns the initial state after parsing and validation.
        """
        workflow_id = str(uuid.uuid4())

        initial_state: ProcurementState = {
            "rfq_id": rfq_id or "",
            "user_id": user_id,
            "workflow_run_id": workflow_id,
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

        config = {"configurable": {"thread_id": workflow_id}}

        try:
            logger.info(f"[WORKFLOW] Starting workflow {workflow_id} for user {user_id}")
            logger.info(f"[WORKFLOW] Input: {user_input[:100]}...")
            
            # Run graph until first interrupt or completion
            result = await self.graph.ainvoke(initial_state, config=config)

            current_step = result.get("current_step")
            logger.info(f"[WORKFLOW] {workflow_id} reached step: {current_step}")
            self._log_workflow_state(workflow_id, result)

            return {
                "workflow_id": workflow_id,
                "state": result,
                "current_step": current_step,
                "parsed_intent": result.get("parsed_intent"),
                "selected_suppliers": result.get("selected_suppliers"),
                "error": result.get("error"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"[WORKFLOW] {workflow_id} failed: {e}", exc_info=True)
            return {
                "workflow_id": workflow_id,
                "error": str(e),
                "current_step": "failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def resume_workflow(
        self,
        workflow_id: str,
        user_decision: str | None = None,
        negotiation_targets: list[dict] | None = None,
    ) -> dict:
        """
        Resume a paused workflow after user decision or external event.
        """
        config = {"configurable": {"thread_id": workflow_id}}

        update_state = {}
        if user_decision:
            update_state["user_decision"] = user_decision
        if negotiation_targets:
            update_state["negotiation_targets"] = negotiation_targets

        try:
            logger.info(f"[WORKFLOW] Resuming workflow {workflow_id}")
            if user_decision:
                logger.info(f"[WORKFLOW] User decision: {user_decision}")
            
            if update_state:
                await self.graph.aupdate_state(config, update_state)

            result = await self.graph.ainvoke(None, config=config)

            current_step = result.get("current_step")
            logger.info(f"[WORKFLOW] {workflow_id} resumed, now at: {current_step}")
            self._log_workflow_state(workflow_id, result)

            return {
                "workflow_id": workflow_id,
                "state": result,
                "current_step": current_step,
                "error": result.get("error"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"[WORKFLOW] {workflow_id} resume failed: {e}", exc_info=True)
            return {
                "workflow_id": workflow_id,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def get_workflow_status(self, workflow_id: str) -> dict:
        """Get comprehensive status of a workflow including all relevant state."""
        config = {"configurable": {"thread_id": workflow_id}}

        try:
            state = await self.graph.aget_state(config)
            values = state.values
            
            status_data = {
                "workflow_id": workflow_id,
                "current_step": values.get("current_step"),
                "status": "running" if state.next else "paused",
                "next_nodes": list(state.next) if state.next else [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                # Key workflow data
                "rfq_id": values.get("rfq_id"),
                "parsed_intent": {
                    "title": values.get("parsed_intent", {}).get("title"),
                    "is_complete": values.get("parsed_intent", {}).get("is_complete"),
                    "items_count": len(values.get("parsed_intent", {}).get("items", [])),
                },
                "selected_suppliers_count": len(values.get("selected_suppliers", [])),
                "quotations_count": len(values.get("quotations", [])),
                "user_decision": values.get("user_decision"),
                "error": values.get("error"),
            }
            
            logger.info(f"[WORKFLOW] Status check for {workflow_id}: {status_data['current_step']} ({status_data['status']})")
            return status_data
        except Exception as e:
            logger.error(f"[WORKFLOW] Failed to get status for {workflow_id}: {e}")
            return {
                "workflow_id": workflow_id,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _log_workflow_state(self, workflow_id: str, state: dict) -> None:
        """Log detailed workflow state for debugging."""
        logger.info(f"[WORKFLOW-STATE] {workflow_id}:")
        logger.info(f"  Current Step: {state.get('current_step')}")
        
        parsed = state.get("parsed_intent", {})
        if parsed:
            logger.info(f"  Parsed Intent: {parsed.get('title')} (complete: {parsed.get('is_complete')})")
            logger.info(f"    Items: {len(parsed.get('items', []))} item(s)")
        
        suppliers = state.get("selected_suppliers", [])
        if suppliers:
            logger.info(f"  Selected Suppliers: {len(suppliers)} supplier(s)")
            for s in suppliers[:3]:  # Log first 3
                logger.info(f"    - {s.get('name')} ({s.get('country')})")
        
        quotations = state.get("quotations", [])
        if quotations:
            logger.info(f"  Quotations: {len(quotations)} quotation(s)")
        
        if state.get("user_decision"):
            logger.info(f"  User Decision: {state.get('user_decision')}")
        
        if state.get("error"):
            logger.warning(f"  Error: {state.get('error')}")


workflow_service = ProcurementWorkflowService()
