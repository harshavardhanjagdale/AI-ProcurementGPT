"""
RFQ Generation Node - Uses LLM to compose professional RFQ emails
customized for each selected supplier.
"""
import logging

from app.agents.state import ProcurementState
from app.ai.llm_client import llm_client

logger = logging.getLogger(__name__)

RFQ_GENERATION_PROMPT = """You are a procurement professional writing an RFQ (Request for Quotation) email.

Generate a professional, clear RFQ email body for the following request:

RFQ Details:
- Title: {title}
- Description: {description}
- Items: {items}
- Budget: {budget}
- Delivery Timeline: {delivery}
- Supplier: {supplier_name} ({supplier_country})

The email should:
1. Be professional and concise
2. Clearly state all requirements
3. Request specific information (unit price, total, delivery time, warranty, payment terms)
4. Include a deadline for response (7 business days)
5. Be customized slightly for the supplier's profile

Return ONLY the email body text (no subject line, no salutation format)."""


async def generate_rfq_emails(state: ProcurementState) -> dict:
    """Generate RFQ email content for each selected supplier."""
    parsed = state["parsed_intent"]
    suppliers = state["selected_suppliers"]

    title = parsed.get("title", "")
    description = parsed.get("description", "")
    items = parsed.get("items", [])
    budget_max = parsed.get("budget_max")
    budget_min = parsed.get("budget_min")
    delivery_days = parsed.get("delivery_deadline_days")

    budget_str = "Not specified"
    if budget_max:
        budget_str = f"{parsed.get('currency', 'USD')} {budget_min or 0:,.0f} - {budget_max:,.0f}"

    delivery_str = f"{delivery_days} days" if delivery_days else "As soon as possible"

    items_str = "\n".join(
        f"  - {item['product_name']}: {item['quantity']} {item.get('unit', 'units')}"
        + (f" ({item['specifications']})" if item.get('specifications') else "")
        for item in items
    )

    drafts = []
    for supplier in suppliers:
        prompt = RFQ_GENERATION_PROMPT.format(
            title=title,
            description=description,
            items=items_str,
            budget=budget_str,
            delivery=delivery_str,
            supplier_name=supplier["name"],
            supplier_country=supplier["country"],
        )

        email_body = await llm_client.generate(
            system_prompt="You are a procurement specialist writing professional emails.",
            user_prompt=prompt,
            temperature=0.6,
            max_tokens=1000,
        )

        drafts.append({
            "supplier_id": supplier["id"],
            "supplier_name": supplier["name"],
            "supplier_email": supplier["email"],
            "email_body": email_body,
        })

    logger.info(f"Generated {len(drafts)} RFQ email drafts")

    return {
        "rfq_email_drafts": drafts,
        "current_step": "generate_rfq_emails",
    }
