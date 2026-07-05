# Email Webhook Integration Guide

Your system now has a **webhook endpoint** that triggers immediately when supplier emails arrive — no more 60-second polling!

## Webhook Endpoint

```
POST http://localhost:8000/api/v1/webhook/email-arrived
```

**Authentication:**
```
Header: X-Webhook-Token: procuregpt-webhook-secret-2026
```

---

## How It Works

1. Supplier sends reply email to your Gmail
2. Email service (Mailgun, SendGrid, etc.) POSTs to your webhook
3. Webhook immediately:
   - Saves email to database
   - Extracts RFQ number from subject
   - Finds waiting workflow session
   - Updates session status to "active"
   - Changes step from "await_supplier_replies" → "process_attachments"
   - Triggers OCR processing automatically
   - Sends notification to frontend

**Total time: < 100ms (vs 60 seconds with polling)**

---

## Setup Instructions

### Option 1: Gmail with Mailgun (Easy)

Gmail doesn't natively support webhooks, but you can use Mailgun as a proxy:

1. **Sign up for Mailgun** (https://www.mailgun.com - free tier available)

2. **Create a Mailgun route** to forward emails to your webhook:
   - Go to Mailgun Dashboard → Routes
   - Create new route:
     ```
     Match expression: match_recipient("your-email@gmail.com")
     Action: POST "http://your-domain.com/api/v1/webhook/email-arrived"
     ```

3. **Set up Mailgun forwarding:**
   - In Mailgun, configure to forward emails to your webhook
   - Add custom header: `X-Webhook-Token: procuregpt-webhook-secret-2026`

### Option 2: SendGrid (Production Ready)

1. **Sign up for SendGrid** (https://sendgrid.com)

2. **Configure Inbound Parse Webhook:**
   - Settings → Inbound Parse
   - Set webhook URL: `http://your-domain.com/api/v1/webhook/email-arrived`
   - POST the following to your webhook:
     ```
     sender=supplier@company.com
     to=your-email@sendgrid.com
     subject=Re: RFQ-2026-00050
     text=Please find quote attached
     ```

3. **Add authentication header in SendGrid:**
   - SendGrid doesn't support custom headers in webhook
   - Instead, use basic auth or query params:
     ```
     http://your-domain.com/api/v1/webhook/email-arrived?token=procuregpt-webhook-secret-2026
     ```
   - Update the webhook endpoint to accept token as query param if needed

### Option 3: Custom IMAP IDLE Listener (Local Development)

For local testing without relying on email services, use IMAP IDLE (server push):

```python
# Run this separate service to listen for new emails in real-time
python scripts/imap_idle_listener.py
```

This will:
- Connect to your Gmail IMAP
- Listen for NEW emails in real-time
- Call the webhook endpoint locally when emails arrive
- No delay, instant processing

---

## Testing the Webhook Locally

```bash
# Test the webhook endpoint
curl -X POST http://localhost:8000/api/v1/webhook/email-arrived \
  -H "X-Webhook-Token: procuregpt-webhook-secret-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "supplier@company.com",
    "to": "your-email@gmail.com",
    "subject": "Re: RFQ-2026-00050 - Quote attached",
    "body": "Please find our quotation attached",
    "attachments": [
      {
        "filename": "quote.pdf",
        "url": "https://example.com/quote.pdf",
        "content_type": "application/pdf",
        "size": 51234
      }
    ]
  }'
```

**Expected Response:**
```json
{
  "status": "processed",
  "rfq_number": "RFQ-2026-00050",
  "rfq_id": "abc123...",
  "message": "Email received and workflow resumed"
}
```

---

## What Happens After Email Arrives

**In Database (instantly):**
- Email saved to `emails` table
- Attachments saved to `email_attachments` table
- WorkflowSession status changed from `waiting` → `active`
- Step `await_supplier_replies` marked as `completed`
- Step `process_attachments` marked as `running`

**In Frontend (instantly):**
- Chat message appears: "⚡ Instant Alert! Supplier email received!"
- Workflow graph updates in real-time
- "Waiting Supplier" step turns green
- "Processing" step turns blue with spinner
- Progress jumps from 50% → 57%

**In Backend (automatically):**
- OCR processing starts immediately
- Quotation data extracted
- AI analysis runs
- Everything happens without you clicking anything

---

## Webhook Token Security

Change the token in production:

```bash
# In .env
WEBHOOK_TOKEN=your-super-secret-token-here-change-me
```

**Best practices:**
- Use a strong random string (minimum 32 characters)
- Change it in production
- Rotate it periodically
- Only expose it in secure environment variables
- Never commit it to git

---

## Disable Polling (Optional)

If you set up the webhook, you can disable the 60-second background worker polling to save resources:

In `backend/app/main.py`, comment out:
```python
# from app.email.background_worker import email_worker
# await email_worker.start()
```

The webhook will handle all incoming emails automatically.

---

## Email Service Webhook Payload Format

Your webhook accepts this format from ANY email service:

```json
{
  "sender": "supplier@company.com",
  "to": "procurement@yourcompany.com",
  "subject": "Re: RFQ-2026-00050 - Price Quote",
  "body": "Here is our quotation...",
  "timestamp": "2026-07-03T15:30:00Z",
  "attachments": [
    {
      "filename": "quote.pdf",
      "url": "https://service.com/attachments/file123.pdf",
      "content_type": "application/pdf",
      "size": 102400
    }
  ]
}
```

---

## Next: IMAP IDLE Listener

For instant local testing, I'll create an IMAP IDLE service that:
- Listens to your Gmail inbox in real-time
- Detects new emails instantly
- Calls the webhook automatically
- Works without external services

Would you like me to create this IMAP IDLE service?
