import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.middleware import RequestLoggingMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Procurement Automation System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled error: {exc}\n{traceback.format_exc()}")
    response = JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {str(exc)}"},
    )
    # Manually add CORS headers
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:3000"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME}


@app.on_event("startup")
async def startup_event():
    logging.info(f"{settings.APP_NAME} starting up...")
    import os
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(f"{settings.UPLOAD_DIR}/email_attachments", exist_ok=True)

    # Start email background worker if IMAP is configured
    if settings.IMAP_USER and settings.IMAP_PASSWORD and settings.IMAP_USER != "your-email@gmail.com":
        from app.email.background_worker import email_worker
        await email_worker.start()
        logging.info("Email polling worker started")


@app.on_event("shutdown")
async def shutdown_event():
    logging.info(f"{settings.APP_NAME} shutting down...")

    # Stop email worker
    from app.email.background_worker import email_worker
    await email_worker.stop()

    from app.database.connection import engine
    await engine.dispose()
