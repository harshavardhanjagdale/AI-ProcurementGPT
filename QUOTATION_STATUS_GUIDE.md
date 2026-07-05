# Quotation Status & Email Checking Guide

## **Quick Answer: What You Need to Do**

When you receive an email with a quotation attachment:

### **Option 1: Automatic (Default)**
- Background worker checks emails every **60 seconds**
- When replies arrive, they're automatically saved to the database
- Quotations are extracted via OCR
- AI analyzes them
- Status automatically updates

### **Option 2: Manual Check (Faster)**
1. Go to **Workflow Monitor** page (or Quotations page)
2. Click **"Check Emails Now"** button
3. System immediately:
   - Checks your inbox for new replies
   - Processes attachments
   - Extracts quotation data via OCR
   - Runs AI analysis
   - Shows you all quotations with rankings

---

## **Three Ways to Check Quotation Status**

### **1. Quotations Dashboard (Easiest)**
**URL:** `http://localhost:3000/dashboard/workflows/quotations?workflow_id={workflow_id}`

**Shows:**
- ✅ All quotations received
- ✅ Price, delivery, warranty, payment terms for each
- ✅ AI ranking (1st, 2nd, 3rd, etc.)
- ✅ AI score (0-100)
- ✅ Which one is recommended
- ✅ "Check Emails Now" button to manually trigger check

**Example flow:**
1. Send RFQ → get workflow_id
2. Wait or click "Check Emails Now"
3. See all supplier quotes with pricing
4. Go to Workflow Monitor to approve/negotiate

### **2. Workflow Monitor Page**
**URL:** `http://localhost:3000/dashboard/workflows?workflow_id={workflow_id}`

**Shows:**
- Current step (e.g., `await_supplier_replies` or `analyze_quotations`)
- Progress through all nodes
- When step is `analyze_quotations` → quotations are being analyzed
- "View Quotations" button links to quotations page

### **3. REST API (For Scripts)**

**Check quotations:**
```bash
curl -X GET "http://localhost:8000/api/v1/chat/workflow/{workflow_id}/quotations" \
  -H "Authorization: Bearer {token}"
```

**Response:**
```json
{
  "workflow_id": "abc123...",
  "rfq_id": "rfq-456...",
  "rfq_number": "RFQ-2026-00001",
  "quotations_count": 3,
  "quotations": [
    {
      "quotation_id": "q1",
      "supplier_name": "TechSupply Corp",
      "total_amount": 5500.00,
      "currency": "USD",
      "delivery_days": 5,
      "ai_ranking": 1,
      "ai_score": 92.5,
      "status": "analyzed"
    },
    {
      "quotation_id": "q2",
      "supplier_name": "GlobalTech",
      "total_amount": 5200.00,
      "currency": "USD",
      "delivery_days": 7,
      "ai_ranking": 2,
      "ai_score": 87.3,
      "status": "analyzed"
    },
    {
      "quotation_id": "q3",
      "supplier_name": "LocalVendor",
      "total_amount": 6100.00,
      "currency": "USD",
      "delivery_days": 3,
      "ai_ranking": 3,
      "ai_score": 81.2,
      "status": "analyzed"
    }
  ]
}
```

**Trigger manual email check:**
```bash
curl -X POST "http://localhost:8000/api/v1/chat/check-emails" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "abc123..."}'
```

**Response:**
```json
{
  "message": "Checked inbox. Found 2 new supplier replies.\nWorkflow abc123... has received replies. Auto-resuming...",
  "emails_found": 2,
  "details": [
    {
      "rfq_number": "RFQ-2026-00001",
      "rfq_id": "rfq-456...",
      "supplier_email": "sales@techsupply.com",
      "attachments_count": 1
    }
  ],
  "workflow_status": {
    "workflow_id": "abc123...",
    "current_step": "process_attachments",
    "status": "resumed"
  }
}
```

---

## **Workflow Stages & When You See Quotations**

| Stage | Status | What's Happening | Next Action |
|-------|--------|------------------|-------------|
| `send_rfq_emails` | 📧 Sending | RFQ emails going to suppliers | Wait for replies |
| `await_supplier_replies` | ⏳ **WAITING** | Workflow paused, checking inbox | Optional: click "Check Emails Now" |
| `process_attachments` | 📄 Processing | OCR extracting quote PDFs | Automatic (1-2 min) |
| `analyze_quotations` | 🤖 Analyzing | AI ranking and scoring quotes | Automatic (1 min) |
| `present_recommendation` | ✅ Ready | Best option selected, awaiting input | Click "Approve" or "Negotiate" |
| `user_decision_gate` | 🛑 **PAUSED** | Workflow waiting for your decision | Make a choice in Quotations page |

---

## **Real Example: Watch It Happen**

### **Timeline:**

**Time 0:00** — You send RFQ
```
GET workflow monitor → Shows: parse_request → validate → select_vendors
```

**Time 0:30** — Emails sent
```
Workflow at: send_rfq_emails (✓ done)
Next: await_supplier_replies (paused, waiting)
```

**Time 5:30** — Supplier replies (you can manually check or wait for background worker)
```
OPTION A: Click "Check Emails Now" → Immediate processing
OPTION B: Wait 60 seconds for background worker → Auto-processing

Workflow transitions:
  await_supplier_replies → process_attachments → analyze_quotations → present_recommendation
```

**Time 6:00** — Check Quotations page
```
Quotations Received:
  1. TechSupply Corp
     💰 $5,500 USD
     📦 5 days delivery
     ⭐ #1 Recommended (AI Score: 92.5/100)
     
  2. GlobalTech
     💰 $5,200 USD
     📦 7 days delivery
     ⭐ #2 (AI Score: 87.3/100)
     
  3. LocalVendor
     💰 $6,100 USD
     📦 3 days delivery
     ⭐ #3 (AI Score: 81.2/100)
```

**Time 6:00** — Workflow Monitor shows
```
Current Step: present_recommendation
Status: running
Next Nodes: user_decision_gate
```

**Time 6:10** — Go to Workflow Monitor, see decision prompt
```
"Recommendation ready! Approve the #1 option, Negotiate, or Cancel?"
```

**Time 6:15** — You click "Approve"
```
Workflow resumes:
  present_recommendation → user_decision_gate → generate_purchase_order → send_po_email → Done!
```

---

## **Troubleshooting**

### **"No quotations yet, where's my email?"**

**Possible causes:**
1. **Background worker hasn't checked yet** — Check every 60 seconds
   - **Solution:** Click "Check Emails Now" to trigger immediately
2. **Email didn't arrive at your account** — Check IMAP config
   - **Solution:** See `.env` file for `IMAP_*` settings
3. **Email arrived but isn't recognized as RFQ reply** — Subject line mismatch
   - **Solution:** Supplier must use `RFQ-YYYY-XXXXX` in subject line

### **"I see an email but no quotation in Quotations page"**

**Possible causes:**
1. **Attachment is still being processed** — OCR + AI analysis takes 1-2 minutes
   - **Solution:** Wait or click refresh button
2. **OCR failed on the PDF** — Not text-extractable
   - **Solution:** Check backend logs for `OCR failed` errors

### **"Workflow is stuck at await_supplier_replies"**

**This is normal!** It's waiting for email replies. Options:
- Click "Check Emails Now" to trigger immediate check
- Wait up to 60 seconds for background worker
- If no emails have arrived yet, supplier hasn't replied

---

## **Best Practices**

✅ **For Testing:**
- Use "Check Emails Now" instead of waiting 60 seconds
- Manually add test quotations to database if needed

✅ **For Production:**
- Background worker checks every 60 seconds automatically
- No manual action needed (fully async)
- OCR processes in background
- AI analysis happens automatically

✅ **For Monitoring:**
- Open Quotations page to see all received quotes
- Use Workflow Monitor to see processing progress
- Use "Check Emails Now" for instant feedback

---

## **Summary**

**When you receive an email:**
1. ✅ System automatically detects it (or click "Check Emails Now")
2. ✅ Attachment is extracted via OCR (1-2 min)
3. ✅ AI ranks all quotes automatically
4. ✅ You see all options in **Quotations Dashboard**
5. ✅ Go to **Workflow Monitor** to approve/negotiate

**No manual data entry needed — everything is automatic!**
