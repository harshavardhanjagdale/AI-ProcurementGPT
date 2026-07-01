from datetime import date, datetime

from pydantic import BaseModel


class RFQItemCreate(BaseModel):
    product_name: str
    specifications: str | None = None
    quantity: int
    unit: str = "units"
    estimated_unit_price: float | None = None


class RFQCreate(BaseModel):
    title: str
    description: str | None = None
    items: list[RFQItemCreate]
    budget_min: float | None = None
    budget_max: float | None = None
    currency: str = "USD"
    delivery_deadline: date | None = None
    supplier_ids: list[str] = []


class RFQFromChatRequest(BaseModel):
    message: str
    rfq_id: str | None = None


class RFQUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    currency: str | None = None
    delivery_deadline: date | None = None


class RFQItemResponse(BaseModel):
    id: str
    product_name: str
    specifications: str | None = None
    quantity: int
    unit: str
    estimated_unit_price: float | None = None

    model_config = {"from_attributes": True}


class RFQSupplierResponse(BaseModel):
    id: str
    supplier_id: str
    status: str
    sent_at: datetime | None = None
    replied_at: datetime | None = None

    model_config = {"from_attributes": True}


class RFQResponse(BaseModel):
    id: str
    rfq_number: str
    user_id: str
    title: str
    description: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    currency: str
    delivery_deadline: date | None = None
    status: str
    ai_workflow_id: str | None = None
    items: list[RFQItemResponse] = []
    suppliers: list[RFQSupplierResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RFQListResponse(BaseModel):
    items: list[RFQResponse]
    total: int
    page: int
    limit: int
    pages: int


class RFQDecisionRequest(BaseModel):
    decision: str  # "approve", "negotiate", "cancel"
    targets: list[dict] | None = None


class RFQChatResponse(BaseModel):
    rfq_id: str
    rfq_number: str
    parsed_data: dict
    ai_message: str
    suggested_suppliers: list[dict] = []
    workflow_id: str | None = None
