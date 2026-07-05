# CRITICAL FIX NEEDED - OCR Workflow Resumption

## Problem Identified

**Why OCR logs are empty:**

1. ✅ Email RECEIVED - webhook detects it
2. ✅ DB UPDATED - session moved to `process_attachments`
3. ❌ **WORKFLOW NOT RESUMED** - LangGraph never invoked!
4. ❌ OCR code never executed - logs empty

**The Gap:**
```
Email arrives → Webhook updates DB → BUT workflow execution never happens
= Frontend polls → sees "process_attachments" status
= BUT that status never actually progresses forward
= STUCK waiting for workflow to be resumed
```

---

## Solution Required

The webhook (`POST /webhook/email-arrived`) needs to:

1. ✅ Save email to DB (DONE)
2. ✅ Update WorkflowSession status (DONE)
3. ❌ **Resume LangGraph workflow with the new email** (MISSING!)

Currently missing: **Call to `/workflow/{session_id}/check-emails` to resume**

---

## Fix Implementation

Update `backend/app/api/v1/webhooks.py` to add workflow resumption:

### After line 170 (where session is updated), add:

```python
# 5. Resume the workflow to process the email
logger.info(f"[WEBHOOK] Resuming workflow for session {ws.id}")

# Import session workflow service
from app.workflows.session_workflow import session_workflow_service

# Resume the workflow with email notification
workflow_result = await session_workflow_service.run_workflow(
    session_id=ws.id,
    user_input=f"Supplier replied to RFQ: {rfq_number}. Processing attached quotation.",
    user_id=ws.user_id,
    db=session
)

logger.info(f"[WEBHOOK] Workflow resumed - now at step: {workflow_result.get('current_step')}")
```

---

## Why This Fix Is Critical

**Current flow:**
```
Email → Webhook updates DB → API polling shows status → But NOTHING happens
= User sees "process_attachments" but OCR never runs
= Logs empty because code never executed
= Workflow stalled indefinitely
```

**Fixed flow:**
```
Email → Webhook updates DB → Workflow resumed → LangGraph processes
→ OCR runs → Logs populated → Progress visible
```

---

## What Happens After Fix

1. Email arrives
2. Webhook saves email
3. Webhook **resumes workflow** with message: "Supplier replied to RFQ..."
4. LangGraph invokes `process_attachments` node
5. OCR runs → **logs start populating**
6. Quotation extracted → recommendation generated
7. Workflow continues to next step

---

## Files to Modify

**File**: `backend/app/api/v1/webhooks.py`

**Location**: After line 170 (where `await self._update_waiting_sessions` is called)

**Add**: Workflow resumption code (shown above)

---

## Status After Fix

✅ Workflow logs will show OCR processing
✅ OCR logs will show extraction details
✅ Frontend will see real-time progress
✅ Quotations will be analyzed automatically
✅ No more "stuck" status

---

## This Is The Root Cause

The webhook was only 80% complete - it updated state but never actually triggered the workflow execution that processes that state!

Now that you know the issue, shall I implement the fix?
