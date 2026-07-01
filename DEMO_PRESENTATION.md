## 1. Executive Summary

**ProcureGPT** is an enterprise-grade AI-powered system that automates the end-to-end procurement lifecycle. It replaces manual RFQ creation, vendor communication, quotation comparison, negotiation, and purchase order generation with an AI-first approach using **LangGraph multi-agent orchestration**.



### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 15, TypeScript, TailwindCSS | Modern reactive UI |
| Backend | FastAPI, Python 3.12, async | High-performance API |
| Database | MySQL 8.0, SQLAlchemy ORM | Relational data store |
| Cache | Redis 7 | Session, queue, rate-limiting |
| AI Engine | LangGraph + OpenAI GPT-4 | Multi-agent orchestration |
| Embeddings | Sentence Transformers (all-MiniLM-L6-v2) | Vendor semantic search |
| OCR | Tesseract + pdf2image | Document text extraction |
| Email | aiosmtplib / imaplib | Bi-directional email |
| PDF Gen | ReportLab | Professional PO documents |

--- guardrail


### Why LangGraph?

- **Stateful execution** — maintains context across steps
- **Human-in-the-loop** — pauses workflow for user decisions
- **Conditional routing** — AI decides next step dynamically
- **Retry & recovery** — built-in error handling per node
- **Persistence** — workflow survives server restarts

### The Workflow State Machine

```
START
  │
  ▼
┌─────────────────────┐     ┌─────────────────────────────────┐
│ 1. PARSE REQUEST    │     │ AI Tool: OpenAI GPT-4           │
│    (NL → Structure) │────▶│ Extracts: items, qty, budget,   │
└─────────────────────┘     │ specs, categories from text     │
  │                         └─────────────────────────────────┘
  ▼
┌─────────────────────┐
│ 2. VALIDATE RFQ     │  (Rule-based: checks completeness)
└─────────────────────┘
  │ ✓ complete             │ ✗ incomplete → ask user
  ▼
┌─────────────────────┐     ┌─────────────────────────────────┐
│ 3. SELECT VENDORS   │     │ AI Tool: Sentence Transformers  │
│    (Semantic Match)  │────▶│ Cosine similarity ranking of   │
└─────────────────────┘     │ supplier embeddings vs query    │
  │                         └─────────────────────────────────┘
  ▼
┌─────────────────────┐     ┌─────────────────────────────────┐
│ 4. GENERATE RFQ     │     │ AI Tool: OpenAI GPT-4           │
│    (Email Drafting)  │────▶│ Writes professional RFQ emails  │
└─────────────────────┘     │ customized per supplier         │
  │                         └─────────────────────────────────┘
  ▼
┌─────────────────────┐
│ 5. SEND EMAILS      │  (Infrastructure: SMTP via aiosmtplib)
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│ 6. AWAIT REPLIES    │  ⏸ INTERRUPT — waits for IMAP inbox
└─────────────────────┘
  │ (emails received)
  ▼
┌─────────────────────┐     ┌─────────────────────────────────┐
│ 7. PROCESS OCR      │     │ AI Tools:                       │
│    (PDF → Data)      │────▶│  • Tesseract (text extraction)  │
└─────────────────────┘     │  • OpenAI GPT-4 (structuring)   │
  │                         └─────────────────────────────────┘
  ▼
┌─────────────────────┐     ┌─────────────────────────────────┐
│ 8. ANALYZE QUOTES   │     │ AI Tool: OpenAI GPT-4           │
│    (Score & Rank)    │────▶│ Multi-criteria scoring (price,  │
└─────────────────────┘     │ delivery, warranty, reliability) │
  │                         └─────────────────────────────────┘
  ▼
┌─────────────────────┐
│ 9. USER DECISION    │  ⏸ INTERRUPT — presents recommendation
└─────────────────────┘
  │
  ├── Accept ──────────▶ [10. GENERATE PO]
  ├── Negotiate ───────▶ [11. NEGOTIATE]
  └── Reject ──────────▶ END
```

---



### Scenario: "Procure 500 Industrial Ball Bearings"

**Step 1** — User types in AI Chat:
> "I need to procure 500 units of industrial ball bearings (6205-2RS type) for our manufacturing line. Budget around $5000-8000. Need delivery within 30 days."

**Step 2** — AI parses & creates RFQ automatically  
**Step 3** — AI selects top 5 suppliers (by embedding similarity)  
**Step 4** — AI generates customized RFQ emails per supplier  
**Step 5** — System sends emails via SMTP  
**Step 6** — Supplier replies with PDF quotation  
**Step 7** — OCR extracts pricing data from PDF  
**Step 8** — AI compares all quotes (score 0-100)  
**Step 9** — User sees recommendation with reasoning  
**Step 10** — User approves → PO auto-generated & emailed  



┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      AI PROCUREMENT AUTOMATION PLATFORM                                                   │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

                                                   ┌──────────────────────┐
                                                   │       End User       │
                                                   │ Procurement Manager  │
                                                   └──────────┬───────────┘
                                                              │
                                                      Natural Language
                                                              │
                                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       PRESENTATION LAYER                                                                   │
│                                                                                                                             │
│                                  Next.js 15 + React + Tailwind CSS                                                         │
│                                                                                                                             │
│  Dashboard │ AI Chat │ Suppliers │ RFQs │ Quotations │ Purchase Orders │ Analytics                                         │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────┘
                                                │
                                            REST APIs
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     APPLICATION LAYER (FastAPI)                                                            │
│                                                                                                                             │
│ Authentication │ RFQ Service │ Supplier Service │ Email Service │ OCR Service │ PO Service │ Notification Service          │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                AI ORCHESTRATION (LangGraph Workflow)                                                       │
│                                                                                                                             │
│   Parse Request                                                                                Generate RFQ                │
│        │                                                                                              │                    │
│        ▼                                                                                              ▼                    │
│   Validate RFQ ─────────► Select Suppliers ─────────► Send Emails ─────────► Wait for Replies         │                    │
│                                                                                                       │                    │
│                                                                                                       ▼                    │
│                     OCR Extraction ◄──────── Receive Quotations (PDF/Email)                           │                    │
│                            │                                                                          │                    │
│                            ▼                                                                          ▼                    │
│                   Compare Quotations ─────────► Recommend Best Supplier ─────────► Generate PO        │                    │
│                                                                                                       │                    │
│                                                                                                       ▼                    │
│                                                                                              Human Approval               │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                              AI SERVICES                                                                    │
│                                                                                                                             │
│  OpenAI GPT-4o                                                                                                              │
│  • Requirement Understanding   through LLM                                                                                              
│  • RFQ Generation                                                                                                            │
│  • Email Drafting                                                                                                            │
│  • Quotation Analysis                                                                                                        │
│  • Negotiation                                                                                                               │
│  • Purchase Order Generation                                                                                                 │
│                                                                                                                             │
│  Sentence Transformers                                                                                                       │
│  • Semantic Supplier Search                                                                                                  │
│  • Vendor Ranking                                                                                                            │
│                                                                                                                             │
│  Tesseract OCR                                                                                                               │
│  • PDF Text Extraction                                                                                                       │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────┘
                                                │
                     ┌──────────────────────────┼────────────────────────────┐
                     │                          │                            │
                     ▼                          ▼                            ▼
        ┌────────────────────┐      ┌────────────────────┐      ┌────────────────────┐
        │      MySQL 8        │      │   SMTP / IMAP      │      │   File Storage      │
        │                     │      │                    │      │ Quotations / PDFs   │
        │ Users               │      │ RFQ Emails         │      │ Purchase Orders     │
        │ Suppliers           │      │ Supplier Replies   │      │ Documents           │
        │ RFQs                │      │ Notifications      │      └────────────────────┘
        │ Quotations          │
        │ Purchase Orders     │
        └────────────────────┘


==============================================================================================================================
                                               END-TO-END AI FLOW
==============================================================================================================================

User Requirement
        │
        ▼
OpenAI GPT extracts procurement requirements
        │
        ▼
Sentence Transformer finds best suppliers
        │
        ▼
GPT generates personalized RFQ emails
        │
        ▼
System sends emails via SMTP
        │
        ▼
Supplier replies with PDF quotation
        │
        ▼
Tesseract OCR extracts quotation details
        │
        ▼
GPT compares quotations (Price • Delivery • Warranty • Quality)
        │
        ▼
AI recommends best supplier
        │
        ▼
Manager approves
        │
        ▼
GPT generates Purchase Order
        │
        ▼
Purchase Order emailed automatically
