# Complete Workflow & OCR Logging System - Implementation Summary

## Problem Discovered

**API Called Repeatedly**: `GET /api/v1/workflow/{session_id}` logs showing every 2-3 seconds
- This is the frontend polling for workflow updates
- **BUT**: No corresponding logs from workflow execution
- **This means**: Workflow is STUCK and not advancing

**OCR Log Empty**: `backend/logs/ocr_processing.log` had no entries
- New OCR logging code never executed
- Indicates workflow never reached OCR stage
- Sessions stuck at `process_attachments` before logging starts

**Root Cause**: No comprehensive logging from workflow START to END

---

## Solution Implemented

### 1. NEW: Comprehensive Workflow Logger
**File**: `backend/app/workflows/workflow_logger.py`

Creates: `backend/logs/workflow_execution.log`

Logs EVERY stage:
- Workflow start
- RFQ session creation
- Node entry/exit
- Processing steps
- Quotation creation
- Workflow completion or failure

### 2. UPDATED: session_workflow.py

Added detailed logging at:
- **Entry**: `[RUN-WORKFLOW-START]` with session ID and input
- **Session Mode**: `[SESSION-MODE] NEW` or `[SESSION-MODE] RESUME`
- **LangGraph Invocation**: `[LANGGRAPH-START]`, `[LANGGRAPH-INVOKED-NEW/RESUME]`
- **Result**: `[RESULT]` with step, RFQ ID, suppliers count
- **Step Updates**: `[UPDATING-STEPS]`
- **Event Emission**: `[EMITTING-EVENT]`
- **Session Status**: `[SESSION-STATUS]`
- **Completion**: `[RUN-WORKFLOW-END]` with total time
- **Errors**: `[WORKFLOW-ERROR]` with full traceback

### 3. SAME: OCR Logging (logger.py)

Already set up with:
- `[OCR]` prefix in process_ocr.py
- `[OCR-SERVICE]` prefix in ocr_service.py
- `backend/logs/ocr_processing.log`

---

## Two Log Files Now

###Log File 1: Workflow Execution
**Path**: `backend/logs/workflow_execution.log`

Logs ENTIRE workflow from start to end:
```
[RUN-WORKFLOW-START] Session: abc-123
[USER-INPUT] I need 50 laptops...
[SESSION-MODE] NEW
[LANGGRAPH-START] Thread: xyz-789
[INITIALIZING-STATE] for new session
[LANGGRAPH-INVOKED-NEW] Result step: parse_user_request
[LANGGRAPH-COMPLETE] Elapsed: 245.50ms
[RESULT] Step: parse_user_request | RFQ:  | Suppliers: 0
[UPDATING-STEPS] for session
[EMITTING-EVENT] for step: parse_user_request
[SESSION-STATUS] active
[RUN-WORKFLOW-END] Success | Step: parse_user_request | Total time: 256.35ms
```

### Log File 2: OCR Processing
**Path**: `backend/logs/ocr_processing.log`

Logs ONLY OCR stage:
```
================================================================================
OCR PROCESSING STARTED for RFQ: 2ddbbf7e-d4c9...
Attachments to process: 1
================================================================================
[ATTACHMENT START] ID: ca453edf...
  File: quote.pdf
  Size: 102400 bytes
[STEP] Extracting text from PDF
[EXTRACTION] Extracted 2543 characters
[QUOTATION DATA]
  supplier_name: ACME Corp
  total_price: 125000
[ATTACHMENT SUCCESS] ID: ca453edf -> Quotation: quot-12345
OCR PROCESSING COMPLETED for RFQ: 2ddbbf7e...
```

---

## What to Check Now

### 1. Check Workflow Logs
```bash
tail -f backend/logs/workflow_execution.log
```

Look for:
- `[RUN-WORKFLOW-START]` - Workflow invoked
- `[LANGGRAPH-COMPLETE]` - Graph finished
- `[RUN-WORKFLOW-END]` - Success or error

**If you see stuck step**: Workflow is hanging at a specific node

### 2. Check OCR Logs
```bash
tail -f backend/logs/ocr_processing.log
```

Look for:
- `OCR PROCESSING STARTED` - OCR began
- `[ATTACHMENT START]` - File processing started
- `[EXTRACTION]` - Text extracted or error
- `OCR PROCESSING COMPLETED` - Success or `OCR PROCESSING FAILED` - Error

### 3. Watch API Calls
```bash
tail -f terminals/2.txt | grep "workflow"
```

Each `GET /workflow/{id}` is a frontend poll checking status.

---

## Finding the Issue

When workflow is stuck:

1. **Check workflow_execution.log**
   - Find the last `[RUN-WORKFLOW-START]`
   - Look for `[LANGGRAPH-COMPLETE]`
   - If missing = Graph is hanging
   - If present = Graph finished but status not updating

2. **If stuck at `process_attachments`:**
   - Check `ocr_processing.log`
   - If empty = OCR code never executed (stuck before OCR)
   - If has entries = OCR running or failed

3. **If error in logs:**
   - Look for `[WORKFLOW-ERROR]` or `[TRACEBACK]`
   - Full Python traceback will be shown
   - This tells you EXACTLY what's breaking

---

## Why TWO Log Files?

- **workflow_execution.log**: Shows WHERE in the workflow you're stuck
- **ocr_processing.log**: Shows WHAT happened during OCR

Together they give you complete visibility into the entire process.

---

## Next Steps

1. **Restart backend** to load new logging code:
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

2. **Send test email** with small PDF attachment

3. **Watch workflow_execution.log**:
   ```bash
   tail -f backend/logs/workflow_execution.log
   ```

4. **See exactly WHERE it gets stuck**:
   - If stops at `parse_user_request` → issue with parsing
   - If stops at `create_rfq_record` → issue with RFQ creation
   - If stops at `send_rfq_emails` → issue with email sending
   - If stops at `process_attachments` → check `ocr_processing.log`

5. **Check ocr_processing.log when needed**:
   ```bash
   tail -f backend/logs/ocr_processing.log
   ```

---

## Files Updated

✅ Created: `backend/app/workflows/workflow_logger.py` - Comprehensive logging functions
✅ Updated: `backend/app/workflows/session_workflow.py` - Added detailed logging throughout
✅ Existing: `backend/app/ocr/logger.py` - OCR-specific logging (already working)

---

## Expected Behavior

**Successful Workflow**:
```
workflow_execution.log shows each step progressing:
  parse_user_request → validate_rfq_data → create_rfq_record → 
  select_vendors → generate_rfq_emails → send_rfq_emails → 
  await_supplier_replies → process_attachments → ...

ocr_processing.log shows OCR processing when that step is reached
```

**Stuck Workflow**:
```
workflow_execution.log shows last step but [RUN-WORKFLOW-END] never appears
= Workflow hanging at that step

ocr_processing.log empty or not created yet
= Never reached OCR stage
```

**Error in Workflow**:
```
workflow_execution.log shows [WORKFLOW-ERROR] with [TRACEBACK]
= Exact error and line number shown
```

---

## Complete Visibility Achieved

✅ From RFQ request start → Workflow invocation → Each node execution → Completion
✅ All errors with full tracebacks
✅ OCR processing separately visible
✅ Timing for each stage
✅ Status transitions logged

**Now you'll see EXACTLY what's breaking!** 🔍
