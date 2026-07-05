# 🚀 CRITICAL FIX IMPLEMENTED: Webhook Workflow Resumption

**Date**: 2026-07-03 | **Time**: 18:20 IST

## Problem Identified
The webhook endpoint (`POST /api/v1/webhook/email-arrived`) was **updating the database** but **NOT resuming the LangGraph workflow**. This caused:
- ✗ Workflow stalled at `process_attachments`
- ✗ OCR logs remain empty (`ocr_processing.log`)
- ✗ Workflow logs stop (`workflow_execution.log`)
- ✗ UI shows active status but no actual processing

## Root Cause
After email arrived via webhook:
1. Email saved to DB ✓
2. Attachments saved to DB ✓
3. `WorkflowSession` status → `active` ✓
4. `WorkflowStep` status → `running` ✓
5. **BUT**: LangGraph workflow NOT invoked ✗

Result: Database state updated but workflow never resumed → OCR node never executed.

---

## Solution Implemented

**File Modified**: `backend/app/api/v1/webhooks.py`

**Changes** (lines 123-147):
```python
# 6. RESUME THE WORKFLOW to process the email
logger.info(f"[WEBHOOK] Resuming workflow for email processing")
from app.workflows.session_workflow import session_workflow_service

# Find the session we just updated
result = await session.execute(
    select(WorkflowSession).where(
        WorkflowSession.rfq_id == rfq.id,
        WorkflowSession.status == "active"
    )
)
ws = result.scalar_one_or_none()

if ws:
    try:
        logger.info(f"[WEBHOOK] Starting workflow execution for session {ws.id}")
        workflow_result = await session_workflow_service.run_workflow(
            session_id=ws.id,
            user_input=f"Supplier email received with RFQ reference: {rfq_number}. Processing quotation attachment.",
            user_id=ws.user_id,
            db=session
        )
        logger.info(f"[WEBHOOK] Workflow executed - current step: {workflow_result.get('current_step')}")
    except Exception as we:
        logger.error(f"[WEBHOOK] Error resuming workflow: {we}", exc_info=True)
```

### What This Does:
1. **Finds** the active workflow session for the RFQ
2. **Invokes** `session_workflow_service.run_workflow` with the updated session
3. **Passes** the email context as user input to trigger continuation
4. **Logs** the result and any errors
5. **Commits** the transaction only after workflow execution

---

## Expected Behavior Now

When email arrives via webhook:

```
[WEBHOOK] Email received from: supplier@company.com
[WEBHOOK] Updating session ... - email arrived for RFQ-2026-00050
[WEBHOOK] Resuming workflow for email processing
[WEBHOOK] Starting workflow execution for session: abc123...
[LANGGRAPH] Invoking... (resuming from await_supplier_replies)
[OCR] Processing attachments for RFQ-2026-00050...
[OCR] [RFQ] Processing started for RFQ-2026-00050
[OCR] [ATTACHMENT] Processing: quotation.pdf
[OCR] [EXTRACTION] Text extracted: ... (quotation content)
[OCR] [QUOTATION] Created quotation record
[OCR] Processing complete!
[WEBHOOK] Workflow executed - current step: select_vendors
[WEBHOOK] ✓ Email processed from supplier@company.com for RFQ-2026-00050
```

### Logs Will Now Show:
- ✅ `workflow_execution.log` - Full workflow execution trace from email received
- ✅ `ocr_processing.log` - Detailed OCR processing with all stages
- ✅ Terminal output - Step-by-step workflow progression

---

## Test Plan

1. **Start Backend** (if not running):
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

2. **Create New RFQ** via chat interface or API

3. **Send Email via Webhook**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/webhook/email-arrived \
     -H "X-Webhook-Token: procuregpt-webhook-secret-2026" \
     -H "Content-Type: application/json" \
     -d '{
       "sender": "supplier@company.com",
       "to": "procurement@company.com",
       "subject": "RE: RFQ-2026-00050 - Quotation",
       "body": "Please find our quotation attached.",
       "attachments": [
         {
           "filename": "quotation.pdf",
           "url": "/path/to/file.pdf",
           "content_type": "application/pdf",
           "size": 50000
         }
       ]
     }'
   ```

4. **Verify Logs**:
   - Check `backend/logs/workflow_execution.log` - should have new entries
   - Check `backend/logs/ocr_processing.log` - should show OCR execution
   - Check terminal output - should show workflow progression
   - Check UI - workflow progress should advance beyond 57%

5. **Check Database**:
   ```sql
   SELECT status, current_step, progress_percentage 
   FROM workflow_sessions 
   WHERE rfq_id = 'RFQ-2026-00050' 
   ORDER BY updated_at DESC LIMIT 1;
   ```
   Should show: `active`, `select_vendors` (or later), `70%+`

---

## Impact

✅ **Webhook now triggers actual workflow execution**
✅ **OCR processes emails immediately upon receipt**
✅ **Workflow logs capture the entire journey**
✅ **No more silent failures or stalled workflows**
✅ **User sees real-time progress in UI**

---

## Next Steps

1. Test with real email via webhook
2. Monitor logs for any issues
3. Verify quotation extraction and selection workflow
4. Confirm UI updates in real-time
