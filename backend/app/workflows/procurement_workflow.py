"""
Procurement Workflow Service - High-level interface for triggering
and managing LangGraph workflow executions.
"""
import logging
import uuid

from app.agents.orchestrator import procurement_graph
from app.agents.state import ProcurementState

logger = logging.getLogger(__name__)


class ProcurementWorkflowService:
    def __init__(self):
        self.graph = procurement_graph

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
            # Run graph until first interrupt or completion
            result = await self.graph.ainvoke(initial_state, config=config)

            logger.info(
                f"Workflow {workflow_id} reached step: {result.get('current_step')}"
            )

            return {
                "workflow_id": workflow_id,
                "state": result,
                "current_step": result.get("current_step"),
                "parsed_intent": result.get("parsed_intent"),
                "selected_suppliers": result.get("selected_suppliers"),
                "error": result.get("error"),
            }
        except Exception as e:
            logger.error(f"Workflow {workflow_id} failed: {e}")
            return {
                "workflow_id": workflow_id,
                "error": str(e),
                "current_step": "failed",
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
            if update_state:
                await self.graph.aupdate_state(config, update_state)

            result = await self.graph.ainvoke(None, config=config)

            logger.info(
                f"Workflow {workflow_id} resumed, now at: {result.get('current_step')}"
            )

            return {
                "workflow_id": workflow_id,
                "state": result,
                "current_step": result.get("current_step"),
                "error": result.get("error"),
            }
        except Exception as e:
            logger.error(f"Workflow resume failed: {e}")
            return {
                "workflow_id": workflow_id,
                "error": str(e),
            }

    async def get_workflow_status(self, workflow_id: str) -> dict:
        """Get current state of a workflow."""
        config = {"configurable": {"thread_id": workflow_id}}

        try:
            state = await self.graph.aget_state(config)
            return {
                "workflow_id": workflow_id,
                "current_step": state.values.get("current_step"),
                "rfq_id": state.values.get("rfq_id"),
                "status": "interrupted" if state.next else "completed",
                "next_nodes": list(state.next) if state.next else [],
            }
        except Exception as e:
            return {
                "workflow_id": workflow_id,
                "error": str(e),
            }


workflow_service = ProcurementWorkflowService()
