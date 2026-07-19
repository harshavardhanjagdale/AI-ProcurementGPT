"""
LLM-based structured data extraction from OCR text.
Converts raw OCR output into structured quotation JSON.
"""
import logging

from langsmith import traceable

from app.ai.llm_client import llm_client

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = "You are a precise document parser. Return only valid JSON."

EXTRACTION_PROMPT = """You are a procurement document parser. Extract structured quotation data from the following OCR text of a supplier quotation PDF.

Return a JSON object with this exact structure:
{{
    "supplier_name": "string or null",
    "quotation_date": "YYYY-MM-DD or null",
    "validity_days": integer or null,
    "currency": "3-letter code like USD, EUR, INR",
    "items": [
        {{
            "product_name": "string",
            "specifications": "string or null",
            "quantity": integer,
            "unit_price": float,
            "total_price": float
        }}
    ],
    "subtotal": float,
    "tax_percent": float or null,
    "tax_amount": float or null,
    "total_amount": float,
    "delivery_days": integer or null,
    "warranty_terms": "string or null",
    "payment_terms": "string or null",
    "additional_notes": "string or null"
}}

Rules:
- Extract ALL line items found in the document
- If a field is not found, set it to null
- Prices should be numeric (no currency symbols)
- If multiple currencies appear, use the primary one
- Parse delivery timelines into integer days (e.g., "2 weeks" = 14)
- "subtotal" is the sum of item totals before tax
- Look for GST, VAT, tax, service tax, CGST, SGST, IGST — extract the combined tax percentage and amount
- "total_amount" should be the grand total INCLUDING tax
- If tax is not mentioned in the document, set tax_percent and tax_amount to null and total_amount = subtotal

CRITICAL — quantity and price accuracy:
- OCR often drops or corrupts table columns. Always cross-check: unit_price × quantity MUST equal total_price for every item.
- If quantity is missing or unclear, compute it as total_price ÷ unit_price (rounded to nearest integer).
- If unit_price seems wrong (e.g. unit_price > total_price, or unit_price × quantity ≠ total_price), recalculate: unit_price = total_price ÷ quantity.
- Between two possible readings of a number, pick the one where unit_price × quantity = total_price.
- Subtotal must equal the sum of all item total_prices. If it doesn't match, re-examine each item's numbers.

OCR Text:
---
{ocr_text}
---
{rfq_context}
Return ONLY the JSON object, no markdown, no explanation."""


class StructuredExtractor:
    @traceable(name="Extract Quotation Data", run_type="llm")
    async def extract_quotation_data(self, ocr_text: str, rfq_items: list[dict] | None = None) -> dict | None:
        """
        Use LLM to extract structured quotation data from raw OCR text.

        Args:
            ocr_text: Raw text output from Tesseract OCR
            rfq_items: Optional list of requested items from the RFQ for cross-reference

        Returns:
            Structured quotation dict or None if extraction fails
        """
        if not ocr_text or len(ocr_text.strip()) < 50:
            logger.warning("OCR text too short for meaningful extraction")
            return None

        rfq_context = ""
        if rfq_items:
            items_text = "\n".join(
                f"- {item['product_name']} (qty: {item['quantity']})"
                for item in rfq_items
            )
            rfq_context = (
                f"\nRFQ REFERENCE — the buyer originally requested these items:\n"
                f"{items_text}\n"
                f"Use these quantities to resolve ambiguity when OCR drops or corrupts the Qty column. "
                f"The supplier usually quotes the same quantities that were requested.\n"
            )

        prompt = EXTRACTION_PROMPT.format(ocr_text=ocr_text[:8000], rfq_context=rfq_context)

        extracted = await llm_client.generate_json(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=2000,
        )

        if extracted is None:
            logger.error("LLM extraction failed or returned unparsable JSON")
            return None

        logger.info(
            f"Extracted quotation: {extracted.get('supplier_name')} "
            f"total={extracted.get('total_amount')} "
            f"items={len(extracted.get('items', []))}"
        )
        return extracted

    async def extract_from_email_body(self, email_body: str) -> dict | None:
        """
        Extract quotation data from an email body (when quote is inline, not PDF).
        Uses same extraction logic but with adjusted expectations.
        """
        if not email_body or len(email_body.strip()) < 30:
            return None

        return await self.extract_quotation_data(email_body)

    async def validate_extraction(self, extracted: dict) -> dict:
        """
        Validate and clean extracted data.
        Returns the data with a confidence score.
        """
        issues = []

        if not extracted.get("total_amount"):
            issues.append("missing_total_amount")
        if not extracted.get("items"):
            issues.append("no_line_items")
        if not extracted.get("currency"):
            extracted["currency"] = "USD"
            issues.append("assumed_usd_currency")

        # Validate item totals
        items = extracted.get("items", [])
        calculated_total = 0
        for item in items:
            if item.get("unit_price") and item.get("quantity"):
                expected_total = item["unit_price"] * item["quantity"]
                item.setdefault("total_price", expected_total)
                calculated_total += item.get("total_price", expected_total)

        if extracted.get("total_amount") and calculated_total > 0:
            discrepancy = abs(extracted["total_amount"] - calculated_total) / extracted["total_amount"]
            if discrepancy > 0.05:
                issues.append(f"total_discrepancy_{discrepancy:.1%}")

        confidence = max(0, 100 - (len(issues) * 15))

        return {
            **extracted,
            "_validation": {
                "confidence": confidence,
                "issues": issues,
                "calculated_total": calculated_total,
            },
        }


structured_extractor = StructuredExtractor()
