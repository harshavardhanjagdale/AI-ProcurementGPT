# ProcureGPT — Enterprise AI Procurement Automation System

## Complete Architecture Documentation

---

## Table of Contents

1. [System Architecture Design](#step-1-system-architecture-design)
2. [MySQL Database Schema](#step-2-mysql-database-schema)
3. [LangGraph Workflow Diagram](#step-3-langgraph-workflow-diagram)
4. [Backend Folder Structure](#step-4-backend-folder-structure)
5. [API Design (REST Endpoints)](#step-5-api-design)

---

## Step 1: System Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Next.js)                              │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌────────────────┐  │
│  │Dashboard │ │RFQ Chat  │ │Supplier   │ │Quotation │ │Purchase Orders │  │
│  │          │ │Interface │ │Management │ │Comparison│ │                │  │
│  └──────────┘ └──────────┘ └───────────┘ └──────────┘ └────────────────┘  │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │ REST API + WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          API GATEWAY (FastAPI)                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │Auth      │ │RFQ       │ │Supplier  │ │Quotation │ │Purchase Order  │  │
│  │Router    │ │Router    │ │Router    │ │Router    │ │Router          │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SERVICE LAYER                                       │
│                                                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │Auth Service  │ │RFQ Service   │ │Supplier Svc  │ │Quotation Service │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────────┘  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │Email Service │ │OCR Service   │ │PO Service    │ │Dashboard Service │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────────┘  │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AI ORCHESTRATION LAYER (LangGraph)                        │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │              Procurement Orchestrator Agent (Graph Root)            │    │
│  └────────────────────────────┬───────────────────────────────────────┘    │
│                               │                                             │
│  ┌──────────┐ ┌──────────┐ ┌─┴────────┐ ┌──────────┐ ┌──────────────┐    │
│  │Vendor    │ │RFQ Gen   │ │Email     │ │OCR       │ │Quotation     │    │
│  │Selection │ │Agent     │ │Agent     │ │Agent     │ │Analysis Agent│    │
│  │Agent     │ │          │ │          │ │          │ │              │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘    │
│  ┌──────────┐ ┌──────────┐                                                │
│  │Negotia-  │ │PO        │                                                │
│  │tion Agent│ │Agent     │                                                │
│  └──────────┘ └──────────┘                                                │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────┐
│   MySQL 8.0      │ │   Redis      │ │  OpenAI API  │
│   (Primary DB)   │ │   (Cache +   │ │  (LLM)       │
│                  │ │    Queue)    │ │              │
└──────────────────┘ └──────────────┘ └──────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────┐
│   SMTP Server    │ │  IMAP Server │ │  Tesseract   │
│   (Send Email)   │ │  (Read Email)│ │  OCR Engine  │
└──────────────────┘ └──────────────┘ └──────────────┘
```

### Architecture Decisions & Justifications

#### OCR Choice: Tesseract (with pdf2image)

| Criteria | Tesseract | Azure Document Intelligence |
|----------|-----------|----------------------------|
| Cost | Free / Open-source | Pay-per-page ($1.50/1000 pages) |
| Deployment | Self-hosted, no external dependency | Requires Azure subscription |
| Accuracy for structured PDFs | High (supplier quotes are typically well-formatted) | Higher for handwritten/complex |
| Latency | Low (local processing) | Network latency added |
| Data Privacy | All data stays local | Data sent to Azure |

**Decision**: Tesseract — supplier quotations are typically well-structured typed PDFs. Self-hosting avoids external costs and data privacy concerns. Tesseract output is augmented with LLM-based structured extraction.

#### Redis Usage

- **Session caching** for authenticated users
- **RFQ state caching** during active LangGraph workflows
- **Email polling queue** — background tasks for IMAP inbox monitoring
- **Rate limiting** for API endpoints

#### Communication Patterns

| Pattern | Use Case |
|---------|----------|
| REST API | All CRUD operations, user interactions |
| WebSocket | Real-time workflow status updates to frontend |
| Background Tasks | Email polling (IMAP), OCR processing |
| Event-driven | Email received → triggers quotation processing |

#### Security Architecture

- JWT-based authentication with refresh tokens
- Role-based access control (Admin, Procurement Manager, Viewer)
- API rate limiting via Redis
- Email credentials encrypted at rest
- Audit logging for all state transitions

### Component Interaction Flow

```
User (NL Input) → FastAPI → LangGraph Orchestrator
                                    │
                    ┌───────────────┼───────────────────┐
                    ▼               ▼                   ▼
            Parse Intent    Query Suppliers     Generate RFQ Email
                    │               │                   │
                    └───────────────┼───────────────────┘
                                    ▼
                            Send Emails (SMTP)
                                    │
                                    ▼
                    Background IMAP Listener (Redis Queue)
                                    │
                                    ▼
                    Email Received → OCR Extraction
                                    │
                                    ▼
                    Quotation Analysis → Score & Rank
                                    │
                                    ▼
                    User Decision (WebSocket notification)
                                    │
                        ┌───────────┴───────────┐
                        ▼                       ▼
                Negotiate (Loop)          Approve → Generate PO
```

### Deployment Architecture (Production)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Nginx      │────▶│  FastAPI    │────▶│  MySQL 8.0  │
│  (Reverse   │     │  (Uvicorn   │     │             │
│   Proxy)    │     │   Workers)  │     └─────────────┘
└─────────────┘     └──────┬──────┘
                           │           ┌─────────────┐
                           ├──────────▶│  Redis      │
                           │           └─────────────┘
                           │           ┌─────────────┐
                           └──────────▶│  Next.js    │
                                       │  (Static /  │
                                       │   Docker)   │
                                       └─────────────┘
```

---

## Step 2: MySQL Database Schema

### Connection Details

- **Host**: localhost
- **User**: root
- **Password**: admin
- **Database**: procuregpt

### Entity-Relationship Diagram

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│    users     │       │    suppliers      │       │supplier_categories│
│──────────────│       │──────────────────│       │──────────────────│
│ id (PK)      │       │ id (PK)          │       │ id (PK)          │
│ email        │       │ name             │◄──────│ supplier_id (FK) │
│ password_hash│       │ email            │       │ category_name    │
│ full_name    │       │ phone            │       │ created_at       │
│ role         │       │ country          │       └──────────────────┘
│ is_active    │       │ rating           │
│ created_at   │       │ avg_delivery_days│
│ updated_at   │       │ status           │
└──────┬───────┘       │ embedding_vector │
       │               │ created_at       │
       │               │ updated_at       │
       │               └────────┬─────────┘
       │                        │
       ▼                        ▼
┌──────────────────┐   ┌──────────────────┐
│      rfqs        │   │   rfq_suppliers  │
│──────────────────│   │──────────────────│
│ id (PK)          │   │ id (PK)          │
│ rfq_number (UQ)  │◄──│ rfq_id (FK)      │
│ user_id (FK)     │   │ supplier_id (FK) │
│ title            │   │ status           │
│ description      │   │ created_at       │
│ budget_min       │   └──────────────────┘
│ budget_max       │
│ currency         │            ┌──────────────────┐
│ delivery_deadline│            │    rfq_items     │
│ status           │◄───────────│──────────────────│
│ ai_workflow_id   │            │ id (PK)          │
│ created_at       │            │ rfq_id (FK)      │
│ updated_at       │            │ product_name     │
└──────┬───────────┘            │ specifications   │
       │                        │ quantity         │
       │                        │ unit             │
       │                        │ created_at       │
       │                        └──────────────────┘
       ▼
┌──────────────────┐       ┌──────────────────────┐
│     emails       │       │  email_attachments   │
│──────────────────│       │──────────────────────│
│ id (PK)          │◄──────│ id (PK)              │
│ rfq_id (FK)      │       │ email_id (FK)        │
│ supplier_id (FK) │       │ file_name            │
│ direction        │       │ file_path            │
│ subject          │       │ file_type            │
│ body             │       │ ocr_processed        │
│ from_address     │       │ ocr_result_json      │
│ to_address       │       │ created_at           │
│ message_id       │       └──────────────────────┘
│ email_type       │
│ sent_at          │
│ created_at       │
└──────────────────┘
       │
       ▼
┌──────────────────┐       ┌──────────────────────┐
│   quotations     │       │  quotation_items     │
│──────────────────│       │──────────────────────│
│ id (PK)          │◄──────│ id (PK)              │
│ rfq_id (FK)      │       │ quotation_id (FK)    │
│ supplier_id (FK) │       │ product_name         │
│ email_id (FK)    │       │ unit_price           │
│ total_amount     │       │ quantity             │
│ currency         │       │ total_price          │
│ delivery_days    │       │ specifications       │
│ warranty_terms   │       │ created_at           │
│ payment_terms    │       └──────────────────────┘
│ validity_days    │
│ ai_score         │
│ ai_ranking       │
│ status           │
│ raw_ocr_text     │
│ created_at       │
│ updated_at       │
└──────────────────┘

┌──────────────────┐       ┌──────────────────────┐
│ purchase_orders  │       │purchase_order_items  │
│──────────────────│       │──────────────────────│
│ id (PK)          │◄──────│ id (PK)              │
│ po_number (UQ)   │       │ po_id (FK)           │
│ rfq_id (FK)      │       │ product_name         │
│ supplier_id (FK) │       │ unit_price           │
│ quotation_id(FK) │       │ quantity             │
│ user_id (FK)     │       │ total_price          │
│ total_amount     │       │ created_at           │
│ currency         │       └──────────────────────┘
│ delivery_date    │
│ payment_terms    │
│ status           │
│ pdf_path         │
│ created_at       │
│ updated_at       │
└──────────────────┘

┌──────────────────┐       ┌──────────────────────┐
│  negotiations    │       │    audit_logs        │
│──────────────────│       │──────────────────────│
│ id (PK)          │       │ id (PK)              │
│ rfq_id (FK)      │       │ user_id (FK)         │
│ supplier_id (FK) │       │ entity_type          │
│ quotation_id(FK) │       │ entity_id            │
│ round_number     │       │ action               │
│ target_price     │       │ old_value            │
│ negotiated_price │       │ new_value            │
│ email_id (FK)    │       │ ip_address           │
│ status           │       │ created_at           │
│ notes            │       └──────────────────────┘
│ created_at       │
│ updated_at       │
└──────────────────┘

┌──────────────────┐
│  chat_history    │
│──────────────────│
│ id (PK)          │
│ user_id (FK)     │
│ rfq_id (FK)      │
│ role             │
│ content          │
│ metadata_json    │
│ created_at       │
└──────────────────┘
```

### Full SQL Schema

```sql
CREATE DATABASE IF NOT EXISTS procuregpt
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE procuregpt;

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
    id CHAR(36) PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role ENUM('admin', 'procurement_manager', 'viewer') NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_users_email (email),
    INDEX idx_users_role (role)
) ENGINE=InnoDB;

-- ============================================================
-- SUPPLIERS
-- ============================================================
CREATE TABLE suppliers (
    id CHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(50),
    country VARCHAR(100) NOT NULL,
    city VARCHAR(100),
    address TEXT,
    rating DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    avg_delivery_days INT UNSIGNED DEFAULT NULL,
    status ENUM('active', 'inactive', 'blacklisted') NOT NULL DEFAULT 'active',
    embedding_vector BLOB NULL,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_suppliers_status (status),
    INDEX idx_suppliers_country (country),
    INDEX idx_suppliers_rating (rating),
    FULLTEXT INDEX ft_suppliers_name (name)
) ENGINE=InnoDB;

-- ============================================================
-- SUPPLIER CATEGORIES
-- ============================================================
CREATE TABLE supplier_categories (
    id CHAR(36) PRIMARY KEY,
    supplier_id CHAR(36) NOT NULL,
    category_name VARCHAR(150) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
    INDEX idx_sc_supplier (supplier_id),
    INDEX idx_sc_category (category_name)
) ENGINE=InnoDB;

-- ============================================================
-- RFQS
-- ============================================================
CREATE TABLE rfqs (
    id CHAR(36) PRIMARY KEY,
    rfq_number VARCHAR(20) NOT NULL UNIQUE,
    user_id CHAR(36) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    budget_min DECIMAL(15,2) NULL,
    budget_max DECIMAL(15,2) NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    delivery_deadline DATE NULL,
    status ENUM(
        'draft', 'vendors_selected', 'rfq_sent',
        'awaiting_quotes', 'quotes_received',
        'analysis_complete', 'negotiation',
        'po_generated', 'completed', 'cancelled'
    ) NOT NULL DEFAULT 'draft',
    ai_workflow_id VARCHAR(255) NULL,
    original_user_input TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_rfqs_user (user_id),
    INDEX idx_rfqs_status (status),
    INDEX idx_rfqs_number (rfq_number),
    INDEX idx_rfqs_created (created_at DESC)
) ENGINE=InnoDB;

-- ============================================================
-- RFQ ITEMS
-- ============================================================
CREATE TABLE rfq_items (
    id CHAR(36) PRIMARY KEY,
    rfq_id CHAR(36) NOT NULL,
    product_name VARCHAR(500) NOT NULL,
    specifications TEXT,
    quantity INT UNSIGNED NOT NULL,
    unit VARCHAR(50) NOT NULL DEFAULT 'units',
    estimated_unit_price DECIMAL(15,2) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE,
    INDEX idx_rfq_items_rfq (rfq_id)
) ENGINE=InnoDB;

-- ============================================================
-- RFQ-SUPPLIER MAPPING
-- ============================================================
CREATE TABLE rfq_suppliers (
    id CHAR(36) PRIMARY KEY,
    rfq_id CHAR(36) NOT NULL,
    supplier_id CHAR(36) NOT NULL,
    status ENUM('selected', 'email_sent', 'replied', 'no_response', 'declined') NOT NULL DEFAULT 'selected',
    sent_at TIMESTAMP NULL,
    replied_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
    UNIQUE KEY uq_rfq_supplier (rfq_id, supplier_id),
    INDEX idx_rfq_suppliers_status (status)
) ENGINE=InnoDB;

-- ============================================================
-- EMAILS
-- ============================================================
CREATE TABLE emails (
    id CHAR(36) PRIMARY KEY,
    rfq_id CHAR(36) NULL,
    supplier_id CHAR(36) NULL,
    direction ENUM('outbound', 'inbound') NOT NULL,
    email_type ENUM('rfq_request', 'supplier_reply', 'negotiation', 'po_delivery', 'general') NOT NULL,
    subject VARCHAR(500) NOT NULL,
    body LONGTEXT NOT NULL,
    from_address VARCHAR(255) NOT NULL,
    to_address VARCHAR(255) NOT NULL,
    cc_addresses TEXT NULL,
    message_id VARCHAR(255) NULL,
    in_reply_to VARCHAR(255) NULL,
    status ENUM('draft', 'sent', 'delivered', 'failed', 'received') NOT NULL DEFAULT 'draft',
    sent_at TIMESTAMP NULL,
    received_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE SET NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
    INDEX idx_emails_rfq (rfq_id),
    INDEX idx_emails_supplier (supplier_id),
    INDEX idx_emails_direction (direction),
    INDEX idx_emails_message_id (message_id),
    INDEX idx_emails_received (received_at DESC)
) ENGINE=InnoDB;

-- ============================================================
-- EMAIL ATTACHMENTS
-- ============================================================
CREATE TABLE email_attachments (
    id CHAR(36) PRIMARY KEY,
    email_id CHAR(36) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size_bytes BIGINT UNSIGNED NULL,
    ocr_processed BOOLEAN NOT NULL DEFAULT FALSE,
    ocr_result_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE,
    INDEX idx_attachments_email (email_id),
    INDEX idx_attachments_ocr (ocr_processed)
) ENGINE=InnoDB;

-- ============================================================
-- QUOTATIONS
-- ============================================================
CREATE TABLE quotations (
    id CHAR(36) PRIMARY KEY,
    rfq_id CHAR(36) NOT NULL,
    supplier_id CHAR(36) NOT NULL,
    email_id CHAR(36) NULL,
    total_amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    delivery_days INT UNSIGNED NULL,
    warranty_terms TEXT NULL,
    payment_terms TEXT NULL,
    validity_days INT UNSIGNED DEFAULT 30,
    ai_score DECIMAL(5,2) NULL,
    ai_ranking INT UNSIGNED NULL,
    ai_analysis_json JSON NULL,
    status ENUM('received', 'under_review', 'shortlisted', 'accepted', 'rejected', 'expired') NOT NULL DEFAULT 'received',
    raw_ocr_text LONGTEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE SET NULL,
    INDEX idx_quotations_rfq (rfq_id),
    INDEX idx_quotations_supplier (supplier_id),
    INDEX idx_quotations_score (ai_score DESC),
    INDEX idx_quotations_status (status)
) ENGINE=InnoDB;

-- ============================================================
-- QUOTATION ITEMS
-- ============================================================
CREATE TABLE quotation_items (
    id CHAR(36) PRIMARY KEY,
    quotation_id CHAR(36) NOT NULL,
    product_name VARCHAR(500) NOT NULL,
    unit_price DECIMAL(15,2) NOT NULL,
    quantity INT UNSIGNED NOT NULL,
    total_price DECIMAL(15,2) NOT NULL,
    specifications TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE CASCADE,
    INDEX idx_qi_quotation (quotation_id)
) ENGINE=InnoDB;

-- ============================================================
-- PURCHASE ORDERS
-- ============================================================
CREATE TABLE purchase_orders (
    id CHAR(36) PRIMARY KEY,
    po_number VARCHAR(20) NOT NULL UNIQUE,
    rfq_id CHAR(36) NOT NULL,
    supplier_id CHAR(36) NOT NULL,
    quotation_id CHAR(36) NOT NULL,
    user_id CHAR(36) NOT NULL,
    total_amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    delivery_date DATE NULL,
    payment_terms TEXT NULL,
    shipping_address TEXT NULL,
    status ENUM('draft', 'approved', 'sent', 'acknowledged', 'fulfilled', 'cancelled') NOT NULL DEFAULT 'draft',
    pdf_path VARCHAR(1000) NULL,
    email_id CHAR(36) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE RESTRICT,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
    FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE SET NULL,
    INDEX idx_po_rfq (rfq_id),
    INDEX idx_po_supplier (supplier_id),
    INDEX idx_po_status (status),
    INDEX idx_po_number (po_number)
) ENGINE=InnoDB;

-- ============================================================
-- PURCHASE ORDER ITEMS
-- ============================================================
CREATE TABLE purchase_order_items (
    id CHAR(36) PRIMARY KEY,
    po_id CHAR(36) NOT NULL,
    product_name VARCHAR(500) NOT NULL,
    unit_price DECIMAL(15,2) NOT NULL,
    quantity INT UNSIGNED NOT NULL,
    total_price DECIMAL(15,2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
    INDEX idx_poi_po (po_id)
) ENGINE=InnoDB;

-- ============================================================
-- NEGOTIATIONS
-- ============================================================
CREATE TABLE negotiations (
    id CHAR(36) PRIMARY KEY,
    rfq_id CHAR(36) NOT NULL,
    supplier_id CHAR(36) NOT NULL,
    quotation_id CHAR(36) NOT NULL,
    round_number INT UNSIGNED NOT NULL DEFAULT 1,
    original_price DECIMAL(15,2) NOT NULL,
    target_price DECIMAL(15,2) NOT NULL,
    negotiated_price DECIMAL(15,2) NULL,
    email_id CHAR(36) NULL,
    reply_email_id CHAR(36) NULL,
    status ENUM('pending', 'sent', 'counter_received', 'accepted', 'rejected', 'expired') NOT NULL DEFAULT 'pending',
    ai_strategy_notes TEXT NULL,
    notes TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
    FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE RESTRICT,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE SET NULL,
    FOREIGN KEY (reply_email_id) REFERENCES emails(id) ON DELETE SET NULL,
    INDEX idx_neg_rfq (rfq_id),
    INDEX idx_neg_supplier (supplier_id),
    INDEX idx_neg_status (status)
) ENGINE=InnoDB;

-- ============================================================
-- AUDIT LOGS
-- ============================================================
CREATE TABLE audit_logs (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id CHAR(36) NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_value JSON NULL,
    new_value JSON NULL,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_audit_entity (entity_type, entity_id),
    INDEX idx_audit_user (user_id),
    INDEX idx_audit_created (created_at DESC),
    INDEX idx_audit_action (action)
) ENGINE=InnoDB;

-- ============================================================
-- CHAT HISTORY
-- ============================================================
CREATE TABLE chat_history (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    rfq_id CHAR(36) NULL,
    role ENUM('user', 'assistant', 'system') NOT NULL,
    content TEXT NOT NULL,
    metadata_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE SET NULL,
    INDEX idx_chat_user (user_id),
    INDEX idx_chat_rfq (rfq_id),
    INDEX idx_chat_created (created_at DESC)
) ENGINE=InnoDB;
```

### Indexing Strategy Summary

| Table | Index Type | Purpose |
|-------|-----------|---------|
| users | UNIQUE on email | Fast login lookup |
| suppliers | FULLTEXT on name | Natural language search |
| suppliers | B-TREE on rating, status, country | Vendor filtering |
| rfqs | B-TREE on status, created_at DESC | Dashboard queries |
| emails | B-TREE on message_id | IMAP deduplication |
| quotations | B-TREE on ai_score DESC | Ranking queries |
| audit_logs | COMPOSITE on (entity_type, entity_id) | Entity history lookup |

---

## Step 3: LangGraph Workflow Diagram

### State Definition

```python
from typing import TypedDict, Literal, Annotated
from langgraph.graph import add_messages

class ProcurementState(TypedDict):
    # Core identifiers
    rfq_id: str
    user_id: str
    workflow_run_id: str

    # User input
    user_input: str
    parsed_intent: dict

    # Vendor selection
    selected_suppliers: list[dict]
    supplier_scores: list[dict]

    # RFQ generation
    rfq_email_drafts: list[dict]
    rfq_emails_sent: bool

    # Quotation processing
    received_emails: list[dict]
    ocr_results: list[dict]
    quotations: list[dict]

    # Analysis
    comparison_matrix: dict
    ai_recommendation: dict
    rankings: list[dict]

    # User decision
    user_decision: Literal["approve", "negotiate", "cancel"] | None
    negotiation_targets: list[dict]

    # Negotiation
    negotiation_round: int
    negotiation_emails_sent: bool
    negotiation_results: list[dict]

    # Purchase order
    po_generated: bool
    po_pdf_path: str | None
    po_email_sent: bool

    # Workflow control
    current_step: str
    error: str | None
    messages: Annotated[list, add_messages]
```

### Complete Workflow Graph

```
                          ┌─────────────┐
                          │   START     │
                          └──────┬──────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  parse_user_request    │  ← LLM: Extract intent + items
                    │  (Intent Parser Node)  │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  validate_rfq_data     │  ← Check completeness
                    │  (Validation Node)     │
                    └────────────┬───────────┘
                                 │
                        ┌────────┴────────┐
                        ▼                 ▼
               [Data Complete]    [Needs Clarification]
                        │                 │
                        │                 ▼
                        │         ┌──────────────┐
                        │         │ ask_user     │ → Returns to parse
                        │         └──────────────┘
                        ▼
           ┌────────────────────────────┐
           │   select_vendors           │  ← Embedding similarity + DB filter
           │   (Vendor Selection Agent) │
           └────────────┬───────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │   generate_rfq_emails      │  ← LLM: Compose professional RFQ
           │   (RFQ Generation Agent)   │
           └────────────┬───────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │   send_rfq_emails          │  ← SMTP Tool: Send to all vendors
           │   (Email Agent - Send)     │
           └────────────┬───────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │   await_supplier_replies   │  ← IMAP Poll / Event Trigger
           │   (Email Agent - Receive)  │  ← INTERRUPT (waits for external)
           └────────────┬───────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │   process_attachments      │  ← Tesseract OCR + PDF parse
           │   (OCR Agent)              │
           └────────────┬───────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │   extract_quotation_data   │  ← LLM: OCR text → structured JSON
           │   (OCR Agent - Extraction) │
           └────────────┬───────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │   analyze_quotations       │  ← LLM: Score on price, delivery,
           │   (Quotation Analysis)     │     warranty, reliability
           └────────────┬───────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │   present_recommendation   │  ← Format comparison for user
           │   (Analysis Output Node)   │
           └────────────┬───────────────┘
                        │
                        ▼
           ┌────────────────────────────┐
           │   user_decision_gate       │  ← INTERRUPT (waits for user input)
           │   (Human-in-the-Loop)      │
           └────────────┬───────────────┘
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
        [approve]  [negotiate]  [cancel]
              │         │         │
              │         ▼         ▼
              │  ┌──────────┐  ┌───────┐
              │  │negotiate │  │ END   │
              │  │_with_    │  │(cancel)│
              │  │suppliers │  └───────┘
              │  └────┬─────┘
              │       │
              │       ▼
              │  ┌──────────────────────┐
              │  │send_negotiation_email│  ← LLM: Generate counter-offer
              │  │(Negotiation Agent)   │
              │  └────────┬─────────────┘
              │           │
              │           ▼
              │  ┌──────────────────────┐
              │  │await_negotiation_    │  ← INTERRUPT (wait for reply)
              │  │reply                 │
              │  └────────┬─────────────┘
              │           │
              │           ▼
              │  ┌──────────────────────┐
              │  │evaluate_counter_     │  ← LLM: Assess counter-offer
              │  │offer                 │
              │  └────────┬─────────────┘
              │           │
              │     ┌─────┴─────┐
              │     ▼           ▼
              │ [acceptable] [another_round]──→ (back to negotiate)
              │     │                            (max 3 rounds)
              │     ▼
              ▼     ▼
     ┌────────────────────────────┐
     │   generate_purchase_order  │  ← Create PO record + PDF
     │   (PO Agent)               │
     └────────────┬───────────────┘
                  │
                  ▼
     ┌────────────────────────────┐
     │   send_po_email            │  ← SMTP: Send PO to supplier
     │   (PO Agent - Delivery)    │
     └────────────┬───────────────┘
                  │
                  ▼
            ┌───────────┐
            │    END    │
            │ (success) │
            └───────────┘
```

### Node-to-Agent Mapping

| Graph Node | Agent | LLM Used? | Tools Required |
|-----------|-------|-----------|----------------|
| `parse_user_request` | Orchestrator | Yes | — |
| `validate_rfq_data` | Orchestrator | No | — |
| `ask_user` | Orchestrator | Yes | — |
| `select_vendors` | Vendor Selection Agent | No (embeddings) | DB query, vector similarity |
| `generate_rfq_emails` | RFQ Generation Agent | Yes | Template engine |
| `send_rfq_emails` | Email Agent | No | SMTP tool |
| `await_supplier_replies` | Email Agent | No | IMAP tool (interrupt) |
| `process_attachments` | OCR Agent | No | Tesseract, pdf2image |
| `extract_quotation_data` | OCR Agent | Yes | — |
| `analyze_quotations` | Quotation Analysis Agent | Yes | — |
| `present_recommendation` | Quotation Analysis Agent | Yes | — |
| `user_decision_gate` | Orchestrator | No | Human interrupt |
| `negotiate_with_suppliers` | Negotiation Agent | Yes | — |
| `send_negotiation_email` | Negotiation Agent | No | SMTP tool |
| `evaluate_counter_offer` | Negotiation Agent | Yes | — |
| `generate_purchase_order` | PO Agent | Yes | ReportLab PDF |
| `send_po_email` | PO Agent | No | SMTP tool |

### Conditional Routing Logic

```python
def route_after_validation(state):
    if state["parsed_intent"].get("is_complete"):
        return "select_vendors"
    return "ask_user"

def route_user_decision(state):
    decision = state["user_decision"]
    if decision == "approve":
        return "generate_purchase_order"
    elif decision == "negotiate":
        return "negotiate_with_suppliers"
    return "__end__"

def route_negotiation_result(state):
    if state["negotiation_results"][-1]["accepted"]:
        return "generate_purchase_order"
    if state["negotiation_round"] >= 3:
        return "present_recommendation"
    return "negotiate_with_suppliers"
```

### Interrupt Points (Human-in-the-Loop)

| Interrupt | Trigger | Resume Mechanism |
|-----------|---------|-----------------|
| `await_supplier_replies` | System waits for IMAP emails | Background worker detects reply → resumes graph |
| `user_decision_gate` | Presents comparison to user | User clicks Approve/Negotiate/Cancel in UI |
| `await_negotiation_reply` | Waits for supplier counter-offer | Background IMAP worker resumes |

### Checkpointing Strategy

```python
from langgraph.checkpoint.mysql import MySQLSaver

checkpointer = MySQLSaver(
    connection_string="mysql+aiomysql://root:admin@localhost/procuregpt"
)

app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["user_decision_gate"],
    interrupt_after=["await_supplier_replies", "await_negotiation_reply"]
)
```

### Error Handling

| Failure | Strategy |
|---------|----------|
| Node Failure | Retry 3x with exponential backoff |
| LLM Timeout | Fallback to template-based generation |
| SMTP Failure | Queue in Redis, retry with backoff |
| OCR Failure | Mark for manual review |
| Workflow Crash | Resume from last checkpoint |
| Max Retries Hit | Notify user, pause workflow |

---

## Step 4: Backend Folder Structure

```
backend/
├── alembic/                          # Database migrations
│   ├── versions/                     # Migration files
│   ├── env.py
│   └── alembic.ini
│
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI application entry point
│   │
│   ├── core/                         # Application configuration & cross-cutting
│   │   ├── __init__.py
│   │   ├── config.py                 # Environment variables & settings (Pydantic)
│   │   ├── security.py              # JWT token generation, password hashing
│   │   ├── dependencies.py          # FastAPI dependency injection
│   │   ├── exceptions.py            # Custom exception classes
│   │   ├── middleware.py            # CORS, rate limiting, logging middleware
│   │   └── constants.py            # Enums, status codes, magic strings
│   │
│   ├── api/                          # REST API Layer (Controllers)
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py            # Aggregated v1 router
│   │   │   ├── auth.py              # POST /login, /register, /refresh
│   │   │   ├── users.py             # GET/PUT /users/me
│   │   │   ├── suppliers.py         # CRUD /suppliers
│   │   │   ├── rfqs.py              # CRUD /rfqs + workflow triggers
│   │   │   ├── quotations.py        # GET /quotations, comparison endpoints
│   │   │   ├── purchase_orders.py   # GET/POST /purchase-orders
│   │   │   ├── negotiations.py      # GET/POST /negotiations
│   │   │   ├── emails.py            # GET /emails (history)
│   │   │   ├── chat.py              # POST /chat (AI conversation)
│   │   │   ├── dashboard.py         # GET /dashboard/stats
│   │   │   └── webhooks.py          # POST /webhooks/email-received
│   │   └── deps.py                  # Route-level dependencies
│   │
│   ├── models/                       # SQLAlchemy ORM Models
│   │   ├── __init__.py
│   │   ├── base.py                  # DeclarativeBase, common mixins
│   │   ├── user.py
│   │   ├── supplier.py
│   │   ├── supplier_category.py
│   │   ├── rfq.py
│   │   ├── rfq_item.py
│   │   ├── rfq_supplier.py
│   │   ├── email.py
│   │   ├── email_attachment.py
│   │   ├── quotation.py
│   │   ├── quotation_item.py
│   │   ├── purchase_order.py
│   │   ├── purchase_order_item.py
│   │   ├── negotiation.py
│   │   ├── audit_log.py
│   │   └── chat_history.py
│   │
│   ├── schemas/                      # Pydantic DTOs (Request/Response)
│   │   ├── __init__.py
│   │   ├── auth.py                  # LoginRequest, TokenResponse
│   │   ├── user.py                  # UserCreate, UserResponse
│   │   ├── supplier.py             # SupplierCreate, SupplierResponse, SupplierList
│   │   ├── rfq.py                  # RFQCreate, RFQResponse, RFQWithItems
│   │   ├── quotation.py           # QuotationResponse, ComparisonMatrix
│   │   ├── purchase_order.py      # POCreate, POResponse
│   │   ├── negotiation.py         # NegotiationRequest, NegotiationResponse
│   │   ├── email.py               # EmailResponse, EmailHistory
│   │   ├── chat.py                # ChatMessage, ChatResponse
│   │   └── dashboard.py           # DashboardStats
│   │
│   ├── repositories/                 # Data Access Layer (DB queries)
│   │   ├── __init__.py
│   │   ├── base.py                  # Generic CRUD repository
│   │   ├── user_repository.py
│   │   ├── supplier_repository.py
│   │   ├── rfq_repository.py
│   │   ├── quotation_repository.py
│   │   ├── email_repository.py
│   │   ├── purchase_order_repository.py
│   │   ├── negotiation_repository.py
│   │   └── audit_repository.py
│   │
│   ├── services/                     # Business Logic Layer
│   │   ├── __init__.py
│   │   ├── auth_service.py          # Login, register, token management
│   │   ├── supplier_service.py     # CRUD + embedding generation
│   │   ├── rfq_service.py          # RFQ lifecycle management
│   │   ├── quotation_service.py    # Quotation CRUD + analysis trigger
│   │   ├── email_service.py        # Send/receive orchestration
│   │   ├── ocr_service.py          # PDF extraction pipeline
│   │   ├── purchase_order_service.py
│   │   ├── negotiation_service.py
│   │   └── dashboard_service.py    # Aggregate stats
│   │
│   ├── agents/                       # LangGraph Agent Definitions
│   │   ├── __init__.py
│   │   ├── state.py                 # ProcurementState TypedDict
│   │   ├── orchestrator.py         # Main graph builder
│   │   ├── nodes/                   # Individual graph nodes
│   │   │   ├── __init__.py
│   │   │   ├── parse_request.py    # Intent parsing node
│   │   │   ├── validate_rfq.py     # Validation node
│   │   │   ├── select_vendors.py   # Vendor selection node
│   │   │   ├── generate_rfq.py     # RFQ email generation node
│   │   │   ├── send_emails.py      # Email sending node
│   │   │   ├── await_replies.py    # IMAP polling node
│   │   │   ├── process_ocr.py      # OCR processing node
│   │   │   ├── extract_data.py     # Structured extraction node
│   │   │   ├── analyze_quotes.py   # Comparison & scoring node
│   │   │   ├── user_decision.py    # Human-in-the-loop node
│   │   │   ├── negotiate.py        # Negotiation node
│   │   │   └── generate_po.py      # PO generation node
│   │   ├── tools/                   # Tools available to agents
│   │   │   ├── __init__.py
│   │   │   ├── db_tools.py         # Query suppliers, save records
│   │   │   ├── email_tools.py      # SMTP send, IMAP read
│   │   │   ├── ocr_tools.py        # Tesseract execution
│   │   │   └── pdf_tools.py        # ReportLab PDF generation
│   │   └── prompts/                 # LLM prompt templates
│   │       ├── __init__.py
│   │       ├── intent_parsing.py
│   │       ├── rfq_generation.py
│   │       ├── quotation_analysis.py
│   │       ├── negotiation.py
│   │       └── po_generation.py
│   │
│   ├── workflows/                    # LangGraph Compiled Workflows
│   │   ├── __init__.py
│   │   ├── procurement_workflow.py  # Full RFQ lifecycle graph
│   │   ├── negotiation_workflow.py  # Sub-graph for negotiation loop
│   │   └── ocr_workflow.py          # Sub-graph for parallel OCR
│   │
│   ├── email/                        # Email Infrastructure
│   │   ├── __init__.py
│   │   ├── smtp_client.py          # SMTP connection & send
│   │   ├── imap_client.py          # IMAP connection & read
│   │   ├── email_parser.py         # Parse inbound emails
│   │   ├── templates/              # Email HTML templates
│   │   │   ├── rfq_request.html
│   │   │   ├── negotiation.html
│   │   │   └── purchase_order.html
│   │   └── background_worker.py    # IMAP polling background task
│   │
│   ├── ocr/                          # OCR Infrastructure
│   │   ├── __init__.py
│   │   ├── tesseract_engine.py     # Tesseract wrapper
│   │   ├── pdf_converter.py        # PDF → images (pdf2image)
│   │   └── structured_extractor.py # LLM-based JSON extraction
│   │
│   ├── ai/                           # AI Utilities
│   │   ├── __init__.py
│   │   ├── llm_client.py           # OpenAI API wrapper
│   │   ├── embeddings.py           # Sentence Transformers wrapper
│   │   └── vector_search.py        # Cosine similarity search
│   │
│   ├── database/                     # Database Configuration
│   │   ├── __init__.py
│   │   ├── session.py              # AsyncSession factory
│   │   ├── connection.py           # Engine creation (MySQL)
│   │   └── redis.py                # Redis connection pool
│   │
│   └── utils/                        # Shared Utilities
│       ├── __init__.py
│       ├── rfq_number_generator.py  # RFQ-YYYY-NNNNN format
│       ├── po_number_generator.py   # PO-YYYY-NNNNN format
│       ├── file_storage.py         # Local file save/retrieve
│       ├── pdf_generator.py        # ReportLab PO PDF creation
│       └── logger.py               # Structured logging setup
│
├── tests/                            # Test Suite
│   ├── __init__.py
│   ├── conftest.py                  # Fixtures, test DB
│   ├── unit/
│   │   ├── test_services/
│   │   ├── test_agents/
│   │   └── test_repositories/
│   ├── integration/
│   │   ├── test_api/
│   │   ├── test_email/
│   │   └── test_workflows/
│   └── fixtures/
│       ├── sample_quotation.pdf
│       └── mock_data.py
│
├── scripts/                          # Utility Scripts
│   ├── seed_suppliers.py            # Populate supplier test data
│   ├── generate_embeddings.py       # Batch embedding generation
│   └── test_email_connection.py     # Verify SMTP/IMAP
│
├── .env.example                      # Environment variable template
├── .gitignore
├── requirements.txt                  # Python dependencies
├── Dockerfile
├── docker-compose.yml               # MySQL + Redis + App
└── pyproject.toml                   # Project metadata
```

```
frontend/
├── public/
│   ├── favicon.ico
│   └── logo.svg
│
├── src/
│   ├── app/                          # Next.js App Router
│   │   ├── layout.tsx               # Root layout
│   │   ├── page.tsx                 # Landing / redirect
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx           # Dashboard shell layout
│   │   │   ├── page.tsx             # Dashboard home
│   │   │   ├── rfqs/
│   │   │   │   ├── page.tsx         # RFQ list
│   │   │   │   ├── new/page.tsx     # Create RFQ (chat interface)
│   │   │   │   └── [id]/page.tsx    # RFQ detail + workflow status
│   │   │   ├── suppliers/
│   │   │   │   ├── page.tsx         # Supplier list
│   │   │   │   └── [id]/page.tsx    # Supplier detail
│   │   │   ├── quotations/
│   │   │   │   ├── page.tsx         # All quotations
│   │   │   │   └── [rfqId]/compare/page.tsx  # Side-by-side comparison
│   │   │   ├── purchase-orders/
│   │   │   │   ├── page.tsx         # PO list
│   │   │   │   └── [id]/page.tsx    # PO detail
│   │   │   └── settings/page.tsx    # User settings
│   │   └── api/                     # Next.js API routes (proxy if needed)
│   │
│   ├── components/                   # Reusable UI Components
│   │   ├── ui/                      # shadcn/ui primitives
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── Footer.tsx
│   │   ├── rfq/
│   │   │   ├── RFQChat.tsx          # AI chat interface for RFQ creation
│   │   │   ├── RFQCard.tsx
│   │   │   ├── RFQTimeline.tsx      # Workflow progress visualization
│   │   │   └── RFQStatusBadge.tsx
│   │   ├── suppliers/
│   │   │   ├── SupplierTable.tsx
│   │   │   ├── SupplierForm.tsx
│   │   │   └── SupplierCard.tsx
│   │   ├── quotations/
│   │   │   ├── QuotationCard.tsx
│   │   │   ├── ComparisonTable.tsx
│   │   │   └── ScoreRadar.tsx       # Radar chart for scoring
│   │   ├── purchase-orders/
│   │   │   ├── POCard.tsx
│   │   │   └── POPreview.tsx
│   │   └── shared/
│   │       ├── DataTable.tsx
│   │       ├── StatusBadge.tsx
│   │       ├── LoadingSpinner.tsx
│   │       └── EmptyState.tsx
│   │
│   ├── hooks/                        # Custom React Hooks
│   │   ├── useAuth.ts
│   │   ├── useRFQ.ts
│   │   ├── useSuppliers.ts
│   │   ├── useQuotations.ts
│   │   ├── useWebSocket.ts         # Real-time workflow updates
│   │   └── useChat.ts              # AI chat state management
│   │
│   ├── services/                     # API Client Layer
│   │   ├── api.ts                   # Axios/fetch base client
│   │   ├── auth.service.ts
│   │   ├── rfq.service.ts
│   │   ├── supplier.service.ts
│   │   ├── quotation.service.ts
│   │   ├── purchase-order.service.ts
│   │   └── chat.service.ts
│   │
│   ├── lib/                          # Utilities
│   │   ├── utils.ts                 # cn(), formatCurrency, etc.
│   │   └── constants.ts
│   │
│   └── types/                        # TypeScript Interfaces
│       ├── auth.ts
│       ├── rfq.ts
│       ├── supplier.ts
│       ├── quotation.ts
│       └── purchase-order.ts
│
├── .env.local.example
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── components.json                   # shadcn/ui config
```

---

## Step 5: API Design (REST Endpoints)

### Base URL: `http://localhost:8000/api/v1`

### Authentication

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/auth/register` | Register new user | No |
| POST | `/auth/login` | Login, get JWT tokens | No |
| POST | `/auth/refresh` | Refresh access token | Refresh Token |
| POST | `/auth/logout` | Invalidate refresh token | Yes |
| GET | `/auth/me` | Get current user profile | Yes |

#### Request/Response Examples:

```json
// POST /auth/register
{
  "email": "john@company.com",
  "password": "securePass123!",
  "full_name": "John Smith",
  "role": "procurement_manager"
}

// Response: 201 Created
{
  "id": "uuid",
  "email": "john@company.com",
  "full_name": "John Smith",
  "role": "procurement_manager",
  "created_at": "2026-06-30T12:00:00Z"
}

// POST /auth/login
{
  "email": "john@company.com",
  "password": "securePass123!"
}

// Response: 200 OK
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### Suppliers

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/suppliers` | List all suppliers (paginated, filterable) | Yes |
| GET | `/suppliers/:id` | Get supplier by ID | Yes |
| POST | `/suppliers` | Create new supplier | Admin/PM |
| PUT | `/suppliers/:id` | Update supplier | Admin/PM |
| DELETE | `/suppliers/:id` | Soft-delete supplier | Admin |
| GET | `/suppliers/search` | Semantic search by category/capability | Yes |
| POST | `/suppliers/:id/regenerate-embedding` | Re-generate embedding | Admin |

#### Query Parameters for GET /suppliers:

```
?page=1&limit=20&status=active&country=India&category=IT+Hardware&min_rating=3.5&sort_by=rating&order=desc
```

#### Request/Response:

```json
// POST /suppliers
{
  "name": "TechSupply Corp",
  "email": "sales@techsupply.com",
  "phone": "+1-555-0123",
  "country": "USA",
  "city": "San Francisco",
  "address": "123 Market St",
  "categories": ["IT Hardware", "Networking Equipment"],
  "avg_delivery_days": 7,
  "notes": "Preferred vendor for laptops and servers"
}

// Response: 201 Created
{
  "id": "uuid",
  "name": "TechSupply Corp",
  "email": "sales@techsupply.com",
  "phone": "+1-555-0123",
  "country": "USA",
  "city": "San Francisco",
  "rating": 0.0,
  "avg_delivery_days": 7,
  "status": "active",
  "categories": ["IT Hardware", "Networking Equipment"],
  "created_at": "2026-06-30T12:00:00Z"
}
```

---

### RFQs (Request for Quotation)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/rfqs` | List all RFQs (paginated) | Yes |
| GET | `/rfqs/:id` | Get RFQ with items and status | Yes |
| POST | `/rfqs` | Create RFQ manually | Yes |
| POST | `/rfqs/from-chat` | Create RFQ via AI chat (natural language) | Yes |
| PUT | `/rfqs/:id` | Update RFQ (draft only) | Yes |
| DELETE | `/rfqs/:id` | Cancel RFQ | Yes |
| POST | `/rfqs/:id/start-workflow` | Trigger LangGraph workflow | Yes |
| GET | `/rfqs/:id/workflow-status` | Get current workflow state | Yes |
| POST | `/rfqs/:id/decision` | Submit user decision (approve/negotiate/cancel) | Yes |
| GET | `/rfqs/:id/timeline` | Get RFQ lifecycle events | Yes |

#### Request/Response:

```json
// POST /rfqs/from-chat
{
  "message": "I need 50 Dell Latitude laptops with 16GB RAM and 512GB SSD. Budget is around $50,000. Need delivery within 3 weeks."
}

// Response: 200 OK
{
  "rfq_id": "uuid",
  "rfq_number": "RFQ-2026-00001",
  "parsed_data": {
    "title": "Dell Latitude Laptops Procurement",
    "items": [
      {
        "product_name": "Dell Latitude Laptop",
        "specifications": "16GB RAM, 512GB SSD",
        "quantity": 50,
        "unit": "units"
      }
    ],
    "budget_max": 50000.00,
    "currency": "USD",
    "delivery_deadline": "2026-07-21"
  },
  "ai_message": "I've created RFQ-2026-00001 for 50 Dell Latitude laptops. I found 5 suitable suppliers. Shall I send the RFQ emails?",
  "suggested_suppliers": [
    {"id": "uuid", "name": "TechSupply Corp", "rating": 4.5, "relevance_score": 0.94}
  ],
  "workflow_id": "wf_uuid"
}

// POST /rfqs/:id/decision
{
  "decision": "negotiate",
  "targets": [
    {"supplier_id": "uuid", "target_price": 45000.00, "reason": "Competitor offered lower"}
  ]
}
```

---

### Quotations

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/quotations` | List all quotations | Yes |
| GET | `/quotations/:id` | Get quotation detail | Yes |
| GET | `/rfqs/:id/quotations` | Get all quotations for an RFQ | Yes |
| GET | `/rfqs/:id/quotations/compare` | Get AI comparison matrix | Yes |
| POST | `/quotations/:id/accept` | Accept a quotation | Yes |
| POST | `/quotations/:id/reject` | Reject a quotation | Yes |

#### Response Example:

```json
// GET /rfqs/:id/quotations/compare
{
  "rfq_id": "uuid",
  "rfq_number": "RFQ-2026-00001",
  "comparison": {
    "quotations": [
      {
        "supplier_name": "TechSupply Corp",
        "total_amount": 47500.00,
        "delivery_days": 14,
        "warranty": "3 years",
        "ai_score": 87.5,
        "ranking": 1,
        "strengths": ["Best warranty", "Fast delivery"],
        "weaknesses": ["Slightly higher price"]
      },
      {
        "supplier_name": "GlobalTech Inc",
        "total_amount": 44000.00,
        "delivery_days": 21,
        "warranty": "1 year",
        "ai_score": 72.3,
        "ranking": 2,
        "strengths": ["Lowest price"],
        "weaknesses": ["Longer delivery", "Short warranty"]
      }
    ],
    "recommendation": {
      "supplier_id": "uuid",
      "supplier_name": "TechSupply Corp",
      "reasoning": "Best overall value considering warranty coverage and faster delivery despite 7% price premium."
    }
  }
}
```

---

### Purchase Orders

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/purchase-orders` | List all POs | Yes |
| GET | `/purchase-orders/:id` | Get PO detail | Yes |
| POST | `/purchase-orders` | Generate PO from accepted quotation | Yes |
| PUT | `/purchase-orders/:id` | Update PO (draft only) | Yes |
| POST | `/purchase-orders/:id/approve` | Approve PO | Admin/PM |
| POST | `/purchase-orders/:id/send` | Send PO to supplier via email | Yes |
| GET | `/purchase-orders/:id/pdf` | Download PO as PDF | Yes |

#### Request/Response:

```json
// POST /purchase-orders
{
  "rfq_id": "uuid",
  "quotation_id": "uuid",
  "supplier_id": "uuid",
  "delivery_date": "2026-07-21",
  "shipping_address": "456 Corporate Blvd, Suite 100",
  "payment_terms": "Net 30"
}

// Response: 201 Created
{
  "id": "uuid",
  "po_number": "PO-2026-00001",
  "rfq_id": "uuid",
  "supplier": {"id": "uuid", "name": "TechSupply Corp"},
  "total_amount": 47500.00,
  "currency": "USD",
  "status": "draft",
  "pdf_path": "/files/po/PO-2026-00001.pdf",
  "created_at": "2026-06-30T12:00:00Z"
}
```

---

### Negotiations

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/negotiations` | List all negotiations | Yes |
| GET | `/rfqs/:id/negotiations` | Get negotiations for RFQ | Yes |
| POST | `/negotiations` | Initiate negotiation | Yes |
| GET | `/negotiations/:id` | Get negotiation detail | Yes |
| POST | `/negotiations/:id/accept` | Accept counter-offer | Yes |
| POST | `/negotiations/:id/counter` | Send another counter | Yes |

---

### Emails

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/emails` | List email history | Yes |
| GET | `/rfqs/:id/emails` | Emails for specific RFQ | Yes |
| GET | `/emails/:id` | Email detail with attachments | Yes |
| POST | `/emails/check-inbox` | Manually trigger inbox check | Admin |

---

### Chat (AI Conversation)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/chat` | Send message to AI agent | Yes |
| GET | `/chat/history` | Get chat history | Yes |
| GET | `/chat/history/:rfq_id` | Get chat for specific RFQ | Yes |
| WebSocket | `/ws/workflow/:rfq_id` | Real-time workflow updates | Yes |

#### Request/Response:

```json
// POST /chat
{
  "message": "What's the status of my laptop RFQ?",
  "rfq_id": "uuid"  // optional context
}

// Response: 200 OK
{
  "response": "RFQ-2026-00001 is currently in 'awaiting_quotes' status. 3 out of 5 suppliers have responded. I'm still waiting for replies from TechSupply Corp and GlobalTech Inc. Would you like me to send a reminder?",
  "metadata": {
    "rfq_id": "uuid",
    "rfq_status": "awaiting_quotes",
    "responses_received": 3,
    "total_suppliers": 5
  }
}
```

---

### Dashboard

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/dashboard/stats` | Overview metrics | Yes |
| GET | `/dashboard/recent-activity` | Latest actions | Yes |
| GET | `/dashboard/rfq-pipeline` | RFQ status distribution | Yes |

#### Response:

```json
// GET /dashboard/stats
{
  "total_rfqs": 45,
  "active_rfqs": 12,
  "total_suppliers": 89,
  "total_po_value": 2450000.00,
  "avg_cycle_time_days": 8.3,
  "rfqs_by_status": {
    "draft": 3,
    "rfq_sent": 5,
    "awaiting_quotes": 4,
    "analysis_complete": 2,
    "completed": 31
  },
  "monthly_savings": 125000.00,
  "savings_percentage": 12.5
}
```

---

### Webhooks (Internal)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/webhooks/email-received` | Called by IMAP worker when new email arrives | Internal Key |

---

### Common Response Patterns

#### Pagination:

```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "limit": 20,
  "pages": 8
}
```

#### Error Response:

```json
{
  "detail": {
    "code": "RFQ_NOT_FOUND",
    "message": "RFQ with id 'xyz' not found",
    "timestamp": "2026-06-30T12:00:00Z"
  }
}
```

#### HTTP Status Codes Used:

| Code | Usage |
|------|-------|
| 200 | Successful GET/PUT |
| 201 | Resource created |
| 204 | Successful DELETE |
| 400 | Validation error |
| 401 | Not authenticated |
| 403 | Not authorized (role) |
| 404 | Resource not found |
| 409 | Conflict (duplicate) |
| 422 | Unprocessable entity |
| 429 | Rate limited |
| 500 | Internal server error |

---

## Implementation Phases

### Phase 1: Auth + Supplier + RFQ (Foundation)
- User registration/login with JWT
- Supplier CRUD with category management
- RFQ creation (manual + basic AI parsing)
- MySQL setup with Alembic migrations
- Basic frontend: login, supplier list, RFQ form

### Phase 2: Email System
- SMTP client for sending RFQ emails
- IMAP client for reading inbox
- Email templates (HTML)
- Background polling worker
- Email-to-RFQ mapping via subject tagging

### Phase 3: OCR + Quotation Parsing
- Tesseract integration with pdf2image
- LLM-based structured extraction
- Quotation record creation
- Attachment management

### Phase 4: AI Comparison Engine
- Full LangGraph workflow implementation
- Vendor selection with embeddings
- Quotation scoring algorithm
- Comparison matrix generation
- AI recommendation engine

### Phase 5: Negotiation + PO Generation
- Negotiation workflow (multi-round)
- AI negotiation email generation
- PO PDF generation (ReportLab)
- PO email delivery
- Dashboard with analytics

---

## Environment Variables (.env)

```bash
# Application
APP_NAME=ProcureGPT
APP_ENV=development
APP_PORT=8000
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=admin
MYSQL_DATABASE=procuregpt

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=app-specific-password
SMTP_FROM_NAME=ProcureGPT

# Email (IMAP)
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your-email@gmail.com
IMAP_PASSWORD=app-specific-password

# Embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2

# File Storage
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=25
```
