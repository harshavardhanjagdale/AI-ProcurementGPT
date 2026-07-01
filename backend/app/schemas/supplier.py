from datetime import datetime

from pydantic import BaseModel, EmailStr


class SupplierCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    country: str
    city: str | None = None
    address: str | None = None
    categories: list[str] = []
    avg_delivery_days: int | None = None
    notes: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    country: str | None = None
    city: str | None = None
    address: str | None = None
    categories: list[str] | None = None
    avg_delivery_days: int | None = None
    rating: float | None = None
    status: str | None = None
    notes: str | None = None


class SupplierCategoryResponse(BaseModel):
    id: str
    category_name: str

    model_config = {"from_attributes": True}


class SupplierResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: str | None = None
    country: str
    city: str | None = None
    address: str | None = None
    rating: float
    avg_delivery_days: int | None = None
    status: str
    categories: list[SupplierCategoryResponse] = []
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierListResponse(BaseModel):
    items: list[SupplierResponse]
    total: int
    page: int
    limit: int
    pages: int


class SupplierSearchQuery(BaseModel):
    query: str
    category: str | None = None
    country: str | None = None
    min_rating: float | None = None
    limit: int = 5
