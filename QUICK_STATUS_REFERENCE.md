# 📋 Quick Status Check Checklist

## When You Receive an Email with a Quote

### Step 1: Check Quotations Status
Go to: **Quotations Dashboard**
```
http://localhost:3000/dashboard/workflows/quotations?workflow_id={your_workflow_id}
```

**What you'll see:**
- ✅ All suppliers who replied
- ✅ Their prices, delivery times, warranty
- ✅ AI ranking (which one is best)
- ✅ AI score for each

### Step 2: If No Quotations Showing
1. Click **"Check Emails Now"** button
2. Wait 2-3 seconds
3. Quotations should appear (if email was received)

### Step 3: Check Workflow Progress
Go to: **Workflow Monitor**
```
http://localhost:3000/dashboard/workflows?workflow_id={your_workflow_id}
```

**What you'll see:**
- Current step in the workflow
- Progress through all stages
- Next pending steps

---

## Status Timeline

```
Email Arrives (in your mailbox)
        ↓
Check Emails Now (or wait 60 sec)
        ↓
process_attachments (OCR extracting)  ~1-2 min
        ↓
analyze_quotations (AI ranking)       ~1 min
        ↓
Quotations Dashboard Updated ✅
        ↓
You Approve/Negotiate
        ↓
Purchase Order Generated
```

---

## API Endpoints You Need

### Get Quotations
```bash
GET http://localhost:8000/api/v1/chat/workflow/{workflow_id}/quotations
Header: Authorization: Bearer {token}
```

### Check Emails Manually
```bash
POST http://localhost:8000/api/v1/chat/check-emails
Header: Authorization: Bearer {token}
Body: {"workflow_id": "{workflow_id}"}
```

### Get Workflow Status
```bash
GET http://localhost:8000/api/v1/chat/workflow/{workflow_id}/status
Header: Authorization: Bearer {token}
```

---

## What Each Status Means

| Status | Meaning | Action |
|--------|---------|--------|
| `await_supplier_replies` | Waiting for emails | Click "Check Emails Now" |
| `process_attachments` | Extracting PDFs | Wait 1-2 minutes |
| `analyze_quotations` | AI ranking quotes | Wait 1 minute |
| `present_recommendation` | Ready for decision | Go to quotations page |
| `user_decision_gate` | Awaiting your input | Click Approve/Negotiate/Cancel |

---

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| "No quotations showing" | Click "Check Emails Now" button |
| "Workflow stuck at await_supplier_replies" | Click "Check Emails Now" or wait 60 sec |
| "Email received but no quotation" | Wait 1-2 min for OCR, then refresh |
| "AI score not showing" | Wait another 1 min for analysis to complete |

---

## Where to Find Things

| What | Where |
|------|-------|
| Quotation prices & details | `/dashboard/workflows/quotations?workflow_id={id}` |
| Workflow progress | `/dashboard/workflows?workflow_id={id}` |
| All RFQs | `/dashboard/rfqs` |
| Email check history | Backend logs with `[WORKFLOW]` prefix |

---

## Quick Command to Test

```bash
# Check if you have any new emails
curl -X POST "http://localhost:8000/api/v1/chat/check-emails" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "YOUR_WORKFLOW_ID"}'

# Response will show:
# - How many emails found
# - Which RFQs have replies
# - Whether workflow was auto-resumed
```

---

**Remember:** Everything is automatic. Email arrives → System processes it → You see it in dashboard. No manual intervention needed!
