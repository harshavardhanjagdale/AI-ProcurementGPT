"""
User Decision Node - Presents analysis to user and waits for decision.
This is an interrupt point in the LangGraph workflow.
"""
import logging

from app.agents.state import ProcurementState

logger = logging.getLogger(__name__)


async def present_recommendation(state: ProcurementState) -> dict:
    """Format the analysis results for user presentation."""
    rankings = state.get("rankings", [])
    recommendation = state.get("ai_recommendation", {})

    if not rankings:
        message = "No quotations have been analyzed yet. Please wait for supplier responses."
    else:
        top = rankings[0] if rankings else {}
        message = (
            f"Analysis complete! I've ranked {len(rankings)} quotations.\n\n"
            f"**Recommended: {recommendation.get('supplier_name', 'N/A')}**\n"
            f"Score: {top.get('score', 0)}/100\n\n"
            f"Reasoning: {recommendation.get('reasoning', 'N/A')}\n\n"
            f"Please choose:\n"
            f"- **Approve** → Generate Purchase Order\n"
            f"- **Negotiate** → Send counter-offers\n"
            f"- **Cancel** → Cancel this RFQ"
        )

    return {
        "current_step": "present_recommendation",
        "messages": [{"role": "assistant", "content": message}],
    }


async def user_decision_gate(state: ProcurementState) -> dict:
    """
    Wait for user decision. This node is an interrupt point.
    The graph pauses here until the user submits approve/negotiate/cancel.
    """
    return {
        "current_step": "user_decision_gate",
    }


def route_user_decision(state: ProcurementState) -> str:
    """Conditional edge: route based on user's decision."""
    decision = state.get("user_decision")

    if decision == "approve":
        return "generate_purchase_order"
    elif decision == "negotiate":
        return "negotiate_with_suppliers"
    else:
        return "__end__"
