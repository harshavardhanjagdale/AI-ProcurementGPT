from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_rfqs: int
    active_rfqs: int
    total_suppliers: int
    total_po_value: float
    avg_cycle_time_days: float | None
    rfqs_by_status: dict[str, int]


class RecentActivity(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    description: str
    created_at: str
