from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.suppliers import router as suppliers_router
from app.api.v1.rfqs import router as rfqs_router
from app.api.v1.emails import router as emails_router
from app.api.v1.quotations import router as quotations_router
from app.api.v1.purchase_orders import router as po_router
from app.api.v1.negotiations import router as negotiations_router
from app.api.v1.chat import router as chat_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.workflows import router as workflows_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.ws import router as ws_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(suppliers_router, prefix="/suppliers", tags=["Suppliers"])
api_router.include_router(rfqs_router, prefix="/rfqs", tags=["RFQs"])
api_router.include_router(emails_router, prefix="/emails", tags=["Emails"])
api_router.include_router(quotations_router, prefix="/quotations", tags=["Quotations"])
api_router.include_router(po_router, prefix="/purchase-orders", tags=["Purchase Orders"])
api_router.include_router(negotiations_router, prefix="/negotiations", tags=["Negotiations"])
api_router.include_router(chat_router, prefix="/chat", tags=["Chat & AI"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(workflows_router, prefix="/workflow", tags=["Workflow Sessions"])
api_router.include_router(webhooks_router, tags=["Webhooks"])
api_router.include_router(ws_router, tags=["WebSocket"])
