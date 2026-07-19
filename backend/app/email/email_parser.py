"""
Parses inbound emails and maps them to RFQ records.
Handles supplier reply detection and attachment classification.
"""
import re
import logging

logger = logging.getLogger(__name__)

RFQ_PATTERN = re.compile(r"(RFQ-\d{4}-\d{5})")
PRICE_PATTERN = re.compile(r"[\$€£₹]\s?[\d,]+\.?\d*|\d[\d,]*\.?\d*\s?(USD|EUR|GBP|INR)")


def extract_rfq_number(subject: str) -> str | None:
    """Extract RFQ number from email subject."""
    match = RFQ_PATTERN.search(subject)
    return match.group(1) if match else None


def extract_supplier_email(from_address: str) -> str:
    """Extract clean email address from 'Name <email>' format."""
    match = re.search(r"<(.+?)>", from_address)
    return match.group(1).lower() if match else from_address.lower().strip()


def classify_attachment(filename: str) -> str:
    """Classify attachment type for processing priority."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        return "quotation_pdf"
    elif ext in ("xlsx", "xls", "csv"):
        return "quotation_spreadsheet"
    elif ext in ("doc", "docx"):
        return "quotation_document"
    elif ext in ("jpg", "jpeg", "png"):
        return "image"
    return "other"


def is_quotation_reply(email_data: dict) -> bool:
    """
    Determine if an inbound email is a quotation reply.
    Checks for RFQ number in subject, attachments, and price mentions.
    Also matches negotiation-response emails (supplier declining to reduce price).
    """
    subject = email_data.get("subject", "")
    body = email_data.get("body", "")
    attachments = email_data.get("attachments", [])

    has_rfq_ref = RFQ_PATTERN.search(subject) is not None
    has_attachments = len(attachments) > 0
    has_price = PRICE_PATTERN.search(body) is not None

    has_quotation_keywords = any(
        kw in body.lower()
        for kw in ["quotation", "quote", "price", "offer", "proposal", "unit price", "total"]
    )

    has_negotiation_keywords = any(
        kw in body.lower()
        for kw in [
            "final price", "final rate", "best price", "best rate",
            "cannot reduce", "can't reduce", "unable to reduce",
            "not possible", "no further discount", "no discount",
            "lowest price", "lowest rate", "cannot offer",
            "regret", "not in a position", "firm price", "firm rate",
            "non-negotiable", "already competitive",
        ]
    )

    if has_rfq_ref and (has_attachments or has_price or has_quotation_keywords or has_negotiation_keywords):
        return True

    return False


def parse_supplier_reply(email_data: dict) -> dict:
    """
    Parse a supplier reply email into structured data.
    Returns metadata for creating quotation records.
    """
    return {
        "rfq_number": extract_rfq_number(email_data.get("subject", "")),
        "supplier_email": extract_supplier_email(email_data.get("from_address", "")),
        "subject": email_data.get("subject", ""),
        "body": email_data.get("body", ""),
        "is_quotation": is_quotation_reply(email_data),
        "attachments": [
            {
                **att,
                "classification": classify_attachment(att.get("file_name", "")),
            }
            for att in email_data.get("attachments", [])
        ],
        "received_at": email_data.get("received_at"),
        "message_id": email_data.get("message_id"),
    }
