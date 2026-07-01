"""
Validate RFQ Node - Checks if parsed intent has all required data
to proceed with vendor selection.
"""
import logging

from app.agents.state import ProcurementState

logger = logging.getLogger(__name__)


async def validate_rfq_data(state: ProcurementState) -> dict:
    """Validate completeness of parsed RFQ data."""
    parsed = state.get("parsed_intent", {})

    if not parsed:
        return {"current_step": "validate_rfq_data", "error": "No parsed intent found"}

    is_complete = parsed.get("is_complete", False)

    if is_complete:
        items = parsed.get("items", [])
        if not items:
            return {
                "parsed_intent": {**parsed, "is_complete": False, "clarification_needed": "Please specify at least one item with product name and quantity."},
                "current_step": "validate_rfq_data",
            }

        for item in items:
            if not item.get("product_name") or not item.get("quantity"):
                return {
                    "parsed_intent": {**parsed, "is_complete": False, "clarification_needed": "Each item needs a product name and quantity."},
                    "current_step": "validate_rfq_data",
                }

    return {
        "parsed_intent": parsed,
        "current_step": "validate_rfq_data",
    }


def route_after_validation(state: ProcurementState) -> str:
    """Conditional edge: route based on validation result."""
    parsed = state.get("parsed_intent", {})
    if parsed.get("is_complete", False):
        return "select_vendors"
    return "ask_user"
