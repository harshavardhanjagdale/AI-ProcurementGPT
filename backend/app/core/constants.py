from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    PROCUREMENT_MANAGER = "procurement_manager"
    VIEWER = "viewer"


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"


class RFQStatus(str, Enum):
    DRAFT = "draft"
    VENDORS_SELECTED = "vendors_selected"
    RFQ_SENT = "rfq_sent"
    AWAITING_QUOTES = "awaiting_quotes"
    QUOTES_RECEIVED = "quotes_received"
    ANALYSIS_COMPLETE = "analysis_complete"
    NEGOTIATION = "negotiation"
    PO_GENERATED = "po_generated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RFQSupplierStatus(str, Enum):
    SELECTED = "selected"
    EMAIL_SENT = "email_sent"
    REPLIED = "replied"
    NO_RESPONSE = "no_response"
    DECLINED = "declined"


class EmailDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class EmailType(str, Enum):
    RFQ_REQUEST = "rfq_request"
    SUPPLIER_REPLY = "supplier_reply"
    NEGOTIATION = "negotiation"
    PO_DELIVERY = "po_delivery"
    GENERAL = "general"


class QuotationStatus(str, Enum):
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    SHORTLISTED = "shortlisted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class POStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class NegotiationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    COUNTER_RECEIVED = "counter_received"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
