# Email Listener Running Successfully ✅

## Status

Your email listener is **actively listening** for new emails and ready to trigger the webhook!

```
2026-07-03 15:29:07 - Connecting to imap.gmail.com:993
2026-07-03 15:29:08 - Connected to IMAP ✓
2026-07-03 15:29:09 - Starting from UID: 18
2026-07-03 15:29:09 - Email listener started (checking every 10s)
2026-07-03 15:29:09 - Listening for new emails...
```

---

## What It Does

**Every 10 seconds** (faster than background worker's 60s):
1. Connects to your Gmail IMAP
2. Checks for new emails
3. When found, automatically POSTs to webhook: `POST /api/v1/webhook/email-arrived`
4. Webhook triggers workflow update
5. Frontend sees instant notification

---

## How to Test It

### Option 1: Send Real Email
1. Keep listener running
2. Send email from supplier to your Gmail
3. Subject must contain: `RFQ-2026-XXXXX`
4. Watch logs for: `Processing email from...` → `Webhook triggered successfully`

### Option 2: Test Webhook Directly
```bash
curl -X POST http://localhost:8000/api/v1/webhook/email-arrived \
  -H "X-Webhook-Token: procuregpt-webhook-secret-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "supplier@acme.com",
    "to": "your-email@gmail.com",
    "subject": "Re: RFQ-2026-00050 - Quote",
    "body": "Here is our quotation",
    "attachments": []
  }'
```

### Option 3: Create Test RFQ
1. Open frontend
2. Send chat: "I need 50 laptops"
3. Wait for system to send RFQ emails
4. Manually forward one back to yourself
5. Watch listener detect it

---

## Success Indicators

When email arrives, you'll see in logs:

```
Processing email from supplier@company.com: Re: RFQ-2026-00050 - Quote
  From: supplier@company.com
  Subject: Re: RFQ-2026-00050 - Quote
  Attachments: 1
✓ Webhook triggered successfully
```

Then in frontend:
- Chat: "⚡ Instant Alert! Supplier email received!"
- Graph: "Waiting" → Green, "Processing" → Blue
- Progress: 50% → 57%

---

## Configuration

The listener checks every **10 seconds** (vs background worker's 60s)

To change interval, edit `email_listener.py`:
```python
POLL_INTERVAL = 10  # Change this number
```

---

## Next Steps

1. **Keep listener running** in terminal
2. **Start backend** in another terminal: `python -m uvicorn app.main:app --reload`
3. **Send test RFQ** through frontend
4. **Watch instant processing** when email arrives

---

## Files

- **`backend/scripts/email_listener.py`** - The listener (NEW)
- **`backend/scripts/imap_idle_listener.py`** - Old IDLE version (deprecated, delete if needed)

---

## Troubleshooting

**"Failed to connect"**
- Check IMAP credentials in .env
- Verify Gmail account allows IMAP
- Check firewall

**"No new emails detected"**
- Make sure sender is different from your Gmail
- Subject must have RFQ number: `RFQ-2026-XXXXX`
- Check inbox for emails

**"Webhook failed"**
- Make sure backend is running: `python -m uvicorn app.main:app --reload`
- Check webhook token matches
- Check backend logs

---

## You're Ready! 🚀

Your system now has **real-time email detection** that calls the webhook instantly when new emails arrive!

Start the listener, send a test, and watch the magic happen! ✨
