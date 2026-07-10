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
    "description": "Detailed description of the procurement request",
    "items": [
        {
            "product_name": "Product name (include brand if mentioned, e.g. 'Dell Latitude Laptop')",
            "specifications": "Technical specs — ALWAYS provide this, see rules below",
            "quantity": integer (default 1 if not specified),
            "unit": "units/kg/liters/etc (default 'units')"
        }
    ],
    "budget_min": float or null,
    "budget_max": float or null,
    "currency": "USD/EUR/INR/etc (default USD)",
    "delivery_deadline_days": integer or null,
    "categories": ["relevant supplier categories"],
    "direct_supplier": "supplier name(s) if user explicitly wants to buy from specific supplier(s); if several are named, list them ALL comma-separated (e.g. 'Alpha Components, TechSupply'); else null",
    "is_complete": true/false
}

IMPORTANT RULES:

specifications field (NEVER leave null):
- If the user provides specs (RAM, screen size, model number, color, etc.), use those exactly.
- If the user mentions a brand + product (e.g. "Dell Latitude laptops"), infer reasonable standard specs: "Dell Latitude series, business-grade, Intel Core i5/i7, 8-16 GB RAM, 256-512 GB SSD, 14-15.6 inch display".
- If the user only says a generic product (e.g. "laptops"), provide a sensible default: "Business laptop, Intel Core i5 or equivalent, 8 GB RAM, 256 GB SSD, 14-15.6 inch display, Windows OS".
- For non-tech items, describe key attributes: size, material, grade, standard, etc.
- NEVER set specifications to null. Always provide a meaningful description.

Other rules:
- The ONLY mandatory fields are: at least one item with a product_name. Everything else is optional.
- If user doesn't mention quantity, default to 1.
- If user doesn't mention budget, currency, or deadline, leave them null. Still mark is_complete as true.
- "direct_supplier" should ONLY be set when the user explicitly names a SUPPLIER/VENDOR they want to buy FROM (e.g. "buy from TechSupply Corp", "order from GlobalTech", "purchase from ErgoSupply").
- Do NOT set direct_supplier for product BRANDS or MANUFACTURERS in the product name. "Dell", "HP", "Lenovo", "Apple", "Samsung", etc. are product brands, NOT supplier names. "Buy 10 Dell laptops" means buy Dell-branded laptops from any supplier — direct_supplier should be null. "Buy 10 laptops from TechSupply" means buy from the supplier TechSupply — direct_supplier should be "TechSupply".
- If the user names MORE THAN ONE supplier (e.g. "from Alpha Components and TechSupply", "order from A, B and C"), include EVERY named supplier in "direct_supplier", comma-separated. Do not drop any.
- NEVER put supplier/vendor names in "title" or "description". Those describe the PRODUCT only (e.g. title "Laptops", not "Laptops from Alpha Components"). The RFQ title and description are shown to every supplier, so naming one supplier there leaks it to the others. Supplier names belong ONLY in the "direct_supplier" field.
- Set is_complete to false ONLY if you cannot identify even a single product/item from the message.
- Be generous with is_complete — if you can figure out what they want to buy, mark it true.

WORKED EXAMPLES (study these carefully — they define the exact behavior expected):

Example 1 — brand in product name is NOT a supplier
User: "I need to buy 10 Dell Latitude laptops for the sales team."
Output:
{
    "title": "Dell Latitude Laptops for Sales Team",
    "description": "Procurement of 10 Dell Latitude business laptops for the sales department.",
    "items": [
        {
            "product_name": "Dell Latitude Laptop",
            "specifications": "Dell Latitude series, business-grade, Intel Core i5/i7, 8-16 GB RAM, 256-512 GB SSD, 14-15.6 inch display, Windows OS",
            "quantity": 10,
            "unit": "units"
        }
    ],
    "budget_min": null,
    "budget_max": null,
    "currency": "USD",
    "delivery_deadline_days": null,
    "categories": ["Electronics", "Computers", "IT Equipment"],
    "direct_supplier": null,
    "is_complete": true
}
Note: "Dell" is a brand in the product name, so direct_supplier stays null.

Example 2 — explicit supplier ("from X") sets direct_supplier, with budget and currency
User: "Order 50 ergonomic office chairs from ErgoSupply Corp, budget max 20000 USD."
Output:
{
    "title": "Ergonomic Office Chairs",
    "description": "Procurement of 50 ergonomic office chairs.",
    "items": [
        {
            "product_name": "Ergonomic Office Chair",
            "specifications": "Adjustable height, lumbar support, breathable mesh back, 5-point base with castors, weight capacity 120 kg",
            "quantity": 50,
            "unit": "units"
        }
    ],
    "budget_min": null,
    "budget_max": 20000,
    "currency": "USD",
    "delivery_deadline_days": null,
    "categories": ["Furniture", "Office Supplies"],
    "direct_supplier": "ErgoSupply Corp",
    "is_complete": true
}
Note: "from ErgoSupply Corp" names a supplier, so direct_supplier is set — but the supplier name is kept OUT of title/description (product only).

Example 3 — another brand-not-supplier case
User: "Purchase 5 HP printers for the accounts department."
Output:
{
    "title": "HP Printers for Accounts Department",
    "description": "Procurement of 5 HP printers for the accounts department.",
    "items": [
        {
            "product_name": "HP Printer",
            "specifications": "HP business laser/inkjet printer, network-capable, duplex printing, A4 support",
            "quantity": 5,
            "unit": "units"
        }
    ],
    "budget_min": null,
    "budget_max": null,
    "currency": "USD",
    "delivery_deadline_days": null,
    "categories": ["Electronics", "Office Equipment"],
    "direct_supplier": null,
    "is_complete": true
}
Note: "HP" is a manufacturer brand, not a supplier — direct_supplier stays null.

Example 4 — budget range, non-USD currency, and a delivery deadline
User: "We need about 200 units of A4 copier paper, budget between 500 and 900 EUR, deliver within 2 weeks."
Output:
{
    "title": "A4 Copier Paper",
    "description": "Procurement of approximately 200 units of A4 copier paper with a delivery deadline of two weeks.",
    "items": [
        {
            "product_name": "A4 Copier Paper",
            "specifications": "A4 size (210 x 297 mm), 80 gsm, white, multipurpose copier/printer paper, 500 sheets per ream",
            "quantity": 200,
            "unit": "units"
        }
    ],
    "budget_min": 500,
    "budget_max": 900,
    "currency": "EUR",
    "delivery_deadline_days": 14,
    "categories": ["Office Supplies", "Stationery"],
    "direct_supplier": null,
    "is_complete": true
}
Note: "between 500 and 900" fills both budget_min and budget_max; "within 2 weeks" -> 14 days.

Example 5 — incomplete request (no identifiable product)
User: "Hi there, can you help me?"
Output:
{
    "title": "Clarification Needed",
    "description": "The user greeting did not specify any product or item to procure.",
    "items": [],
    "budget_min": null,
    "budget_max": null,
    "currency": "USD",
    "delivery_deadline_days": null,
    "categories": [],
    "direct_supplier": null,
    "is_complete": false
}
Note: no product can be identified, so is_complete is false and items is empty.

Example 6 — multiple distinct items in one request
User: "Buy 3 standing desks and 3 monitor arms for the new hires."
Output:
{
    "title": "Standing Desks and Monitor Arms for New Hires",
    "description": "Procurement of 3 standing desks and 3 monitor arms for onboarding new hires.",
    "items": [
        {
            "product_name": "Standing Desk",
            "specifications": "Height-adjustable sit-stand desk, electric motor, 120 x 60 cm desktop, memory presets",
            "quantity": 3,
            "unit": "units"
        },
        {
            "product_name": "Monitor Arm",
            "specifications": "Single-monitor desk-mount arm, VESA 75/100, gas-spring, supports up to 32 inch / 9 kg",
            "quantity": 3,
            "unit": "units"
        }
    ],
    "budget_min": null,
    "budget_max": null,
    "currency": "USD",
    "delivery_deadline_days": null,
    "categories": ["Furniture", "Office Equipment"],
    "direct_supplier": null,
    "is_complete": true
}
Note: two separate items, each with its own quantity and specifications.

Example 7 — generic product needs sensible default specs
User: "I need 20 laptops."
Output:
{
    "title": "Laptops",
    "description": "Procurement of 20 general-purpose business laptops.",
    "items": [
        {
            "product_name": "Business Laptop",
            "specifications": "Business laptop, Intel Core i5 or equivalent, 8 GB RAM, 256 GB SSD, 14-15.6 inch display, Windows OS",
            "quantity": 20,
            "unit": "units"
        }
    ],
    "budget_min": null,
    "budget_max": null,
    "currency": "USD",
    "delivery_deadline_days": null,
    "categories": ["Electronics", "Computers", "IT Equipment"],
    "direct_supplier": null,
    "is_complete": true
}
Note: no specs given, so provide reasonable defaults; never leave specifications null.

Example 8 — non-tech / industrial item with attributes
User: "Get me 500 kg of 304-grade stainless steel sheets from MetalWorks Ltd."
Output:
{
    "title": "304 Stainless Steel Sheets",
    "description": "Procurement of 500 kg of 304-grade stainless steel sheets.",
    "items": [
        {
            "product_name": "Stainless Steel Sheet (304 Grade)",
            "specifications": "304-grade stainless steel, cold-rolled, 2B finish, standard sheet thickness 1-2 mm",
            "quantity": 500,
            "unit": "kg"
        }
    ],
    "budget_min": null,
    "budget_max": null,
    "currency": "USD",
    "delivery_deadline_days": null,
    "categories": ["Raw Materials", "Metals", "Industrial Supplies"],
    "direct_supplier": "MetalWorks Ltd",
    "is_complete": true
}
Note: describe material attributes (grade, finish, thickness); unit is "kg"; "from MetalWorks Ltd" sets direct_supplier.

Follow the exact structure, field names, and decision logic shown in these examples for every request you parse."""


async def parse_user_request(state: ProcurementState) -> dict:
    """Parse natural language input into structured RFQ data."""
    user_input = state["user_input"]

    logger.info(f"Parsing user request: {user_input[:100]}...")

    parsed = await llm_client.generate_json(
        system_prompt=PARSE_SYSTEM_PROMPT,
        user_prompt=user_input,
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


async def parse_and_validate(state: ProcurementState) -> dict:
    """
    Merged graph node: parse the natural-language request AND validate it in a single
    step, so the trace (LangSmith) and the UI show one "Understand Request" node instead
    of two. Internally it just composes the existing parse + validate logic unchanged.
    """
    from app.agents.nodes.validate_rfq import validate_rfq_data

    out: dict = {}
    parsed = await parse_user_request(state)
    out.update(parsed)
    validated = await validate_rfq_data({**state, **out})
    out.update(validated)
    out["current_step"] = "parse_request"
    return out
