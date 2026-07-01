# ProcureGPT — Backend

AI-Powered Procurement Automation System built with FastAPI, MySQL, and LangGraph.

## Quick Start

### Prerequisites

- Python 3.12+
- MySQL 8.0+
- Redis 7+
- Docker & Docker Compose (optional, for MySQL/Redis)

### 1. Start Infrastructure

```bash
docker-compose up -d
```

This starts MySQL (port 3306) and Redis (port 6379).

### 2. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
copy .env.example .env
# Edit .env with your settings (MySQL credentials are pre-configured for Docker)
```

### 5. Initialize Database

```bash
python -m scripts.init_db
```

### 6. Seed Sample Data

```bash
python -m scripts.seed_suppliers
```

### 7. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

### 8. Access API Docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

## Project Structure

```
backend/
├── app/
│   ├── api/v1/          # REST API routes
│   ├── core/            # Config, security, middleware
│   ├── models/          # SQLAlchemy ORM models
│   ├── schemas/         # Pydantic DTOs
│   ├── repositories/    # Data access layer
│   ├── services/        # Business logic
│   ├── agents/          # LangGraph agents (Phase 4)
│   ├── workflows/       # LangGraph workflows (Phase 4)
│   ├── email/           # Email SMTP/IMAP (Phase 2)
│   ├── ocr/             # Tesseract OCR (Phase 3)
│   ├── ai/              # LLM & embeddings (Phase 4)
│   ├── database/        # DB connection & session
│   └── utils/           # Shared utilities
├── alembic/             # Database migrations
├── scripts/             # Utility scripts
└── tests/               # Test suite
```

## API Endpoints (Phase 1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | Register user |
| POST | /api/v1/auth/login | Login |
| POST | /api/v1/auth/refresh | Refresh token |
| GET | /api/v1/auth/me | Current user |
| GET | /api/v1/suppliers | List suppliers |
| POST | /api/v1/suppliers | Create supplier |
| GET | /api/v1/suppliers/:id | Get supplier |
| PUT | /api/v1/suppliers/:id | Update supplier |
| DELETE | /api/v1/suppliers/:id | Delete supplier |
| GET | /api/v1/rfqs | List RFQs |
| POST | /api/v1/rfqs | Create RFQ |
| GET | /api/v1/rfqs/:id | Get RFQ |
| PUT | /api/v1/rfqs/:id | Update RFQ |
| DELETE | /api/v1/rfqs/:id | Cancel RFQ |
| GET | /api/v1/dashboard/stats | Dashboard stats |
