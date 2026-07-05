"""
Comprehensive Workflow Logging - Logs every step from RFQ creation to completion
Log file: backend/logs/workflow_execution.log
"""
import logging
from pathlib import Path
from datetime import datetime


def setup_workflow_logger():
    """Setup comprehensive workflow logger."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "workflow_execution.log"
    
    # Create logger
    workflow_logger = logging.getLogger("workflow_executor")
    workflow_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    workflow_logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler
    workflow_logger.addHandler(file_handler)
    
    return workflow_logger


# Global logger instance
workflow_logger = setup_workflow_logger()


def log_workflow_start(session_id: str, rfq_id: str, title: str):
    """Log workflow execution start."""
    workflow_logger.info("="*100)
    workflow_logger.info(f"WORKFLOW EXECUTION STARTED")
    workflow_logger.info(f"  Session ID: {session_id}")
    workflow_logger.info(f"  RFQ ID: {rfq_id}")
    workflow_logger.info(f"  Title: {title}")
    workflow_logger.info("="*100)


def log_node_start(node_name: str, display_name: str):
    """Log node execution start."""
    workflow_logger.info(f"\n[NODE-START] {node_name} ({display_name})")
    workflow_logger.debug(f"  Timestamp: {datetime.now()} IST")


def log_node_step(node_name: str, step: str, details: str = ""):
    """Log a step within node execution."""
    msg = f"[{node_name}] {step}"
    if details:
        msg += f" | {details}"
    workflow_logger.info(msg)


def log_node_complete(node_name: str, output: dict = None):
    """Log node completion."""
    workflow_logger.info(f"[NODE-COMPLETE] {node_name} ✓")
    if output:
        for key, value in output.items():
            if key not in ["error", "error_traceback"]:
                workflow_logger.debug(f"  {key}: {str(value)[:200]}")


def log_node_error(node_name: str, error: Exception, traceback_str: str = ""):
    """Log node error."""
    workflow_logger.error(f"[NODE-ERROR] {node_name} FAILED")
    workflow_logger.error(f"  Exception: {type(error).__name__}: {str(error)}")
    if traceback_str:
        workflow_logger.error(f"[TRACEBACK]\n{traceback_str}")


def log_ocr_node_details(attachment_id: str, file_name: str, step: str, details: str = ""):
    """Log OCR node specific details."""
    msg = f"[OCR-NODE] Attachment: {file_name}"
    msg += f" | Step: {step}"
    if details:
        msg += f" | {details}"
    workflow_logger.info(msg)


def log_quotation_created(quotation_id: str, supplier_name: str, price: float):
    """Log quotation creation."""
    workflow_logger.info(f"[QUOTATION-CREATED] ID: {quotation_id}")
    workflow_logger.info(f"  Supplier: {supplier_name}")
    workflow_logger.info(f"  Price: {price}")


def log_workflow_complete(session_id: str, final_step: str, duration_seconds: float):
    """Log workflow completion."""
    workflow_logger.info("\n" + "="*100)
    workflow_logger.info(f"WORKFLOW EXECUTION COMPLETED")
    workflow_logger.info(f"  Session ID: {session_id}")
    workflow_logger.info(f"  Final Step: {final_step}")
    workflow_logger.info(f"  Total Duration: {duration_seconds:.2f} seconds")
    workflow_logger.info("="*100)


def log_workflow_failed(session_id: str, failed_at_node: str, error: str):
    """Log workflow failure."""
    workflow_logger.error("\n" + "="*100)
    workflow_logger.error(f"WORKFLOW EXECUTION FAILED")
    workflow_logger.error(f"  Session ID: {session_id}")
    workflow_logger.error(f"  Failed at Node: {failed_at_node}")
    workflow_logger.error(f"  Error: {error}")
    workflow_logger.error("="*100)


def log_session_status_check(session_id: str, status: str, step: str, progress: float):
    """Log when session status is checked (API calls)."""
    workflow_logger.debug(f"[STATUS-CHECK] Session: {session_id}")
    workflow_logger.debug(f"  Status: {status} | Step: {step} | Progress: {progress}%")
