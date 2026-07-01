"""
Parse User Request Node - Uses LLM to extract structured RFQ data
from natural language user input.
"""
import logging

from app.agents.state import ProcurementState
from app.ai.llm_client import llm_client

logger = logging.getLogger(__name__)

PARSE_SYSTEM_PROMPT = """You are a procurement assistant. Parse the user's natural language request into a structured RFQ (Request for Quotation).

Return a JSON object with:
{
    "title": "Short title for the RFQ",
    "description": "Detailed description",
    "items": [
        {
            "product_name": "Product name",
            "specifications": "Technical specs or null",
            "quantity": integer,
            "unit": "units/kg/liters/etc"
        }
    ],
    "budget_min": float or null,
    "budget_max": float or null,
    "currency": "USD/EUR/INR/etc",
    "delivery_deadline_days": integer or null,
    "categories": ["relevant supplier categories"],
    "is_complete": true/false (false if critical info is missing)
}

If the request is unclear or missing critical information (like product name or quantity), set is_complete to false and add a "clarification_needed" field explaining what's missing."""


async def parse_user_request(state: ProcurementState) -> dict:
    """Parse natural language input into structured RFQ data."""
    user_input = state["user_input"]

    logger.info(f"Parsing user request: {user_input[:100]}...")

    parsed = await llm_client.generate_json(
        system_prompt=PARSE_SYSTEM_PROMPT,
        user_prompt=user_input,
        temperature=0.1,
    )

    if parsed is None:
        return {
            "parsed_intent": {
                "is_complete": False,
                "clarification_needed": "I couldn't understand your request. Please describe what you need to procure.",
                "error": True,
            },
            "current_step": "parse_user_request",
        }

    logger.info(f"Parsed intent: {parsed.get('title')} - complete: {parsed.get('is_complete')}")

    return {
        "parsed_intent": parsed,
        "current_step": "parse_user_request",
    }
