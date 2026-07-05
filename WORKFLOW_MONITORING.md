# Workflow Monitoring Guide

## Quick Overview

Your ProcureGPT system now has **complete workflow visibility** without needing LangSmith. Here's how to monitor workflows in real-time:

---

## **Method 1: Web Dashboard (Easiest)**

### From Chat
1. Send a message to start an RFQ
2. You'll get back a `workflow_url` in the response
3. Click it to open the **Workflow Monitor** page
4. Auto-refreshes every 2 seconds showing:
   - Current step (with description)
   - Progress through all 15 workflow nodes
   - RFQ details (title, items, suppliers, quotations)
   - User decisions
   - Any errors

### Manual Navigation
Go to: `http://localhost:3000/dashboard/workflows?workflow_id={workflow_id}`

---

## **Method 2: REST API (For Scripts/Integrations)**

### Get Workflow Status
```bash
curl -X GET "http://localhost:8000/api/v1/chat/workflow/{workflow_id}/status" \
  -H "Authorization: Bearer {your_token}"
```

### Response
```json
{
  "workflow_id": "abc123...",
  "current_step": "await_supplier_replies",
  "status": "running",
  "rfq_id": "rfq-456...",
  "parsed_intent": {
    "title": "Procurement of Laptops",
    "is_complete": true,
    "items_count": 1
  },
  "selected_suppliers_count": 5,
  "quotations_count": 3,
  "user_decision": null,
  "error": null,
  "timestamp": "2026-07-02T01:22:00Z",
  "next_nodes": ["process_attachments"]
}
```

---

## **Method 3: Server Logs (For Debugging)**

### Enhanced Logging
The backend now logs workflow state transitions with `[WORKFLOW]` prefix:

```
[WORKFLOW] Starting workflow {workflow_id} for user {user_id}
[WORKFLOW] Input: Buy 10 HP laptops from TechSupply...
[WORKFLOW] {workflow_id} reached step: select_vendors
[WORKFLOW-STATE] {workflow_id}:
  Current Step: select_vendors
  Parsed Intent: Procurement of Laptops (complete: true)
    Items: 1 item(s)
  Selected Suppliers: 5 supplier(s)
    - TechSupply Corp (USA)
    - GlobalTech Ltd (India)
    - ...
```

### View in Terminal
```bash
# In your backend terminal, you'll see logs like:
# [WORKFLOW] Starting workflow 7f8b9e3d-...
# [WORKFLOW-STATE] 7f8b9e3d-...: 
#   Current Step: generate_rfq_emails
#   Parsed Intent: Laptops for Office (complete: true)
#   Selected Suppliers: 5 supplier(s)
```

---

## **Workflow States Explained**

| Step | Description | What's Happening |
|------|-------------|------------------|
| `parse_user_request` | Parsing your natural language | LLM converts "buy X from Y" to structured data |
| `validate_rfq_data` | Validating RFQ data | Ensures product name + quantity exist |
| `resolve_direct_supplier` | Finding direct supplier | Looks up supplier if you named one |
| `create_rfq_record` | Creating RFQ in DB | Saves to MySQL with RFQ number |
| `select_vendors` | Selecting best vendors | Finds top 5 suppliers via AI similarity search |
| `generate_rfq_emails` | Generating emails | LLM creates professional RFQ emails |
| `send_rfq_emails` | Sending to suppliers | SMTP sends emails to 5 suppliers |
| `await_supplier_replies` | ⏳ Waiting for responses | IMAP checks inbox for replies (can take hours) |
| `process_attachments` | Processing quotations | OCR extracts text from PDF attachments |
| `analyze_quotations` | Analyzing quotes | LLM compares prices, delivery, terms |
| `present_recommendation` | Preparing recommendation | Creates ranking with best option highlighted |
| `user_decision_gate` | ⏸️ **PAUSED** - Awaiting your input | You decide: approve/negotiate/cancel |
| `negotiate_with_suppliers` | Negotiating | LLM sends counter-offers to selected suppliers |
| `generate_purchase_order` | Creating PO | Generates official PO document |
| `send_po_email` | Sending PO | Emails PO to selected supplier |

---

## **Two Common Flows**

### Flow 1: Generic RFQ (Multi-Vendor)
```
parse → validate → create_rfq → select_vendors (5 best)
→ generate_rfq → send_emails → await_replies (email check loop)
→ process_ocr → analyze → present_recommendation
→ user_decision_gate (PAUSED: you choose supplier)
→ generate_po → send_po_email
```

### Flow 2: Direct Purchase (Single Supplier)
```
parse → validate → resolve_direct_supplier
→ create_rfq → select_vendors (skipped, supplier set)
→ generate_rfq → send_emails → await_replies
→ ... (same as above)
```

---

## **Real Example: Watching a Workflow**

### 1. Start workflow via chat
**You:** "Buy 5 MacBook Pro 16" from Apple Inc"

**Backend:** Returns workflow_id = `abc123def456`

### 2. Open monitor
Click the workflow link or navigate to:
```
http://localhost:3000/dashboard/workflows?workflow_id=abc123def456
```

### 3. Watch it progress
- **Seconds 0-2:** `parse_user_request` → `validate_rfq_data` → `resolve_direct_supplier`
- **Seconds 2-3:** `create_rfq_record` → `select_vendors` (skipped, single supplier)
- **Seconds 3-5:** `generate_rfq_emails` → `send_rfq_emails` (emails sent to Apple)
- **Status:** Now in `await_supplier_replies` (WAITING FOR EMAIL RESPONSE)
  - Dashboard shows: "Status: running" with next node as `process_attachments`
  - Will auto-check inbox every few minutes for reply

### 4. When reply arrives
- IMAP finds Apple's reply email
- Status changes to `process_attachments`
- OCR extracts quote from PDF
- LLM analyzes it
- Status hits `user_decision_gate` (PAUSED)
- You see dashboard prompt: "Approve? Negotiate? Cancel?"

### 5. You approve
- Click "Approve" button
- Workflow resumes to `generate_purchase_order` → `send_po_email` → Done!

---

## **Do You Need LangSmith?**

**Answer: No, not for local development.**

| Feature | Local Solution | LangSmith |
|---------|---|---|
| Real-time status | ✅ Dashboard + API | ✅ Web UI |
| Node-by-node progress | ✅ Logs + Dashboard | ✅ Trace viewer |
| Error tracking | ✅ Error fields in response | ✅ Error analytics |
| Performance metrics | ❌ Not built | ✅ Built-in |
| Team collaboration | ❌ Not needed yet | ✅ Yes |
| Production monitoring | ⚠️ Limited | ✅ Production-grade |

**When to use LangSmith:** If you deploy to production and need team visibility, detailed metrics, and A/B testing of prompts. For now, your local solution is sufficient!

---

## **Quick Commands**

### Check workflow via CLI
```bash
# Get status of a running workflow
curl -s "http://localhost:8000/api/v1/chat/workflow/abc123-def456/status" \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.current_step'

# Output: "await_supplier_replies"
```

### Watch logs in real-time
```bash
# Terminal 1 (backend):
uvicorn app.main:app --reload
# Look for [WORKFLOW] prefixed lines
```

### Reset/Restart a workflow
```bash
# There's no built-in reset yet, but you can:
# 1. Check the workflow_id
# 2. Clear checkpoints from memory (or DB if persisted)
# 3. Start a new workflow
```

---

## **Troubleshooting**

### "Workflow stuck at await_supplier_replies"
- **Expected:** It's waiting for email responses (could be hours)
- **Solution:** Set up a demo email or manually add test replies to database

### "Cannot see current_step in logs"
- Make sure you're using `[WORKFLOW]` prefix when grepping
- Check backend terminal is running with `--reload` flag

### "API returns 404 on status endpoint"
- Ensure workflow_id is correct (copy from chat response)
- Check Authorization header has valid token

---

## **Summary**

✅ **You have everything needed:**
- Dashboard monitor page with auto-refresh
- REST API for programmatic access
- Detailed server logs with `[WORKFLOW]` markers
- Full state visibility at each step
- No additional tools needed (no LangSmith required for local dev)

**Next Step:** Open your chat, send an RFQ, and click the workflow link to see it in action!
