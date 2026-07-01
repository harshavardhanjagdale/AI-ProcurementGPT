from datetime import datetime, timezone


def generate_rfq_number(sequence: int) -> str:
    year = datetime.now(timezone.utc).year
    return f"RFQ-{year}-{sequence:05d}"


def generate_po_number(sequence: int) -> str:
    year = datetime.now(timezone.utc).year
    return f"PO-{year}-{sequence:05d}"
