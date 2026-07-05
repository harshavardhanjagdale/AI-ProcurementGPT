"""
LLM-based structured data extraction from OCR text.
Converts raw OCR output into structured quotation JSON.
"""
import logging

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
- Be precise with quantities and prices

OCR Text:
---
{ocr_text}
---

Return ONLY the JSON object, no markdown, no explanation."""


class StructuredExtractor:
    async def extract_quotation_data(self, ocr_text: str) -> dict | None:
        """
        Use LLM to extract structured quotation data from raw OCR text.

        Args:
            ocr_text: Raw text output from Tesseract OCR

        Returns:
            Structured quotation dict or None if extraction fails
        """
        if not ocr_text or len(ocr_text.strip()) < 50:
            logger.warning("OCR text too short for meaningful extraction")
            return None

        prompt = EXTRACTION_PROMPT.format(ocr_text=ocr_text[:8000])

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
