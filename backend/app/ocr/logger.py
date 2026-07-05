"""
OCR Logging Module - Creates detailed logs for OCR processing
Logs to: backend/logs/ocr_processing.log
"""
import logging
import os
from datetime import datetime
from pathlib import Path


def setup_ocr_logger():
    """Setup dedicated OCR logger that writes to file."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "ocr_processing.log"
    
    # Create logger
    ocr_logger = logging.getLogger("ocr_processor")
    ocr_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    ocr_logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(funcName)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler
    ocr_logger.addHandler(file_handler)
    
    return ocr_logger


# Global logger instance
ocr_logger = setup_ocr_logger()


def log_ocr_start(rfq_id: str, attachment_count: int):
    """Log OCR processing start."""
    ocr_logger.info("="*80)
    ocr_logger.info(f"OCR PROCESSING STARTED for RFQ: {rfq_id}")
    ocr_logger.info(f"Attachments to process: {attachment_count}")
    ocr_logger.info("="*80)


def log_attachment_start(attachment_id: str, file_name: str, file_size: int):
    """Log when starting to process an attachment."""
    ocr_logger.info(f"\n[ATTACHMENT START] ID: {attachment_id}")
    ocr_logger.info(f"  File: {file_name}")
    ocr_logger.info(f"  Size: {file_size} bytes")
    ocr_logger.info(f"  Timestamp: {datetime.now()} IST")


def log_ocr_step(step: str, details: str = ""):
    """Log OCR processing step."""
    msg = f"[STEP] {step}"
    if details:
        msg += f" | {details}"
    ocr_logger.info(msg)


def log_extraction_result(text_length: int, confidence: float = None):
    """Log text extraction results."""
    msg = f"[EXTRACTION] Extracted {text_length} characters"
    if confidence:
        msg += f" | Confidence: {confidence:.2%}"
    ocr_logger.info(msg)


def log_quotation_data(quotation_data: dict):
    """Log extracted quotation data."""
    ocr_logger.info(f"[QUOTATION DATA]")
    for key, value in quotation_data.items():
        ocr_logger.info(f"  {key}: {value}")


def log_attachment_success(attachment_id: str, quotation_id: str = ""):
    """Log successful attachment processing."""
    msg = f"[ATTACHMENT SUCCESS] ID: {attachment_id}"
    if quotation_id:
        msg += f" -> Quotation: {quotation_id}"
    ocr_logger.info(msg)


def log_attachment_error(attachment_id: str, error: Exception, traceback_str: str = ""):
    """Log attachment processing error."""
    ocr_logger.error(f"[ATTACHMENT ERROR] ID: {attachment_id}")
    ocr_logger.error(f"  Exception: {type(error).__name__}: {str(error)}")
    if traceback_str:
        ocr_logger.error(f"  Traceback:\n{traceback_str}")


def log_ocr_complete(rfq_id: str, successful: int, failed: int, total_time_seconds: float):
    """Log OCR processing completion."""
    ocr_logger.info("\n" + "="*80)
    ocr_logger.info(f"OCR PROCESSING COMPLETED for RFQ: {rfq_id}")
    ocr_logger.info(f"Results: {successful} successful, {failed} failed")
    ocr_logger.info(f"Total processing time: {total_time_seconds:.2f} seconds")
    ocr_logger.info("="*80)


def log_ocr_failure(rfq_id: str, error: Exception, traceback_str: str = ""):
    """Log OCR processing failure."""
    ocr_logger.error("\n" + "="*80)
    ocr_logger.error(f"OCR PROCESSING FAILED for RFQ: {rfq_id}")
    ocr_logger.error(f"Exception: {type(error).__name__}: {str(error)}")
    if traceback_str:
        ocr_logger.error(f"Traceback:\n{traceback_str}")
    ocr_logger.error("="*80)


def generate_ocr_report(rfq_id: str, results: list, total_time_seconds: float):
    """Generate OCR review report."""
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    
    report = f"""

{'='*80}
OCR PROCESSING REVIEW REPORT
{'='*80}

RFQ ID: {rfq_id}
Processing Date: {datetime.now()} IST
Total Processing Time: {total_time_seconds:.2f} seconds

SUMMARY:
--------
Total Attachments: {len(results)}
Successful: {len(successful)}
Failed: {len(failed)}
Success Rate: {(len(successful)/len(results)*100):.1f}% if len(results) > 0 else "N/A"

SUCCESSFUL ATTACHMENTS:
-----------------------
"""
    
    for i, result in enumerate(successful, 1):
        report += f"\n{i}. {result.get('file_name', 'Unknown')}\n"
        report += f"   - Extracted text length: {result.get('text_length', 0)} chars\n"
        report += f"   - Quotation ID: {result.get('quotation_id', 'N/A')}\n"
    
    if failed:
        report += f"\n\nFAILED ATTACHMENTS:\n"
        report += "-"*40 + "\n"
        for i, result in enumerate(failed, 1):
            report += f"\n{i}. {result.get('file_name', 'Unknown')}\n"
            report += f"   - Error: {result.get('error', 'Unknown error')}\n"
    
    report += f"\n{'='*80}\nEND OF REPORT\n{'='*80}\n"
    
    ocr_logger.info(report)
    return report
