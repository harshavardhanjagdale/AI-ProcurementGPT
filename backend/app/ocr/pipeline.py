"""
OCR Pipeline - Combines PDF conversion, Tesseract OCR, and LLM extraction
into a single end-to-end processing flow.
"""
import logging
from pathlib import Path

from app.ocr.pdf_converter import pdf_converter
from app.ocr.tesseract_engine import tesseract_engine
from app.ocr.structured_extractor import structured_extractor

logger = logging.getLogger(__name__)


class OCRPipeline:
    """
    Full OCR pipeline:
    1. Convert PDF → images
    2. Run Tesseract OCR on each page
    3. Combine text from all pages
    4. Use LLM to extract structured quotation data
    """

    async def process_pdf(self, pdf_path: str) -> dict:
        """
        Process a PDF file through the full OCR pipeline.

        Returns:
            dict with raw_text, extracted_data, and metadata
        """
        path = Path(pdf_path)
        if not path.exists():
            return {"error": f"File not found: {pdf_path}", "success": False}

        logger.info(f"Starting OCR pipeline for: {pdf_path}")

        # Step 1: Convert PDF to images
        images = pdf_converter.pdf_to_images(pdf_path)
        if not images:
            return {"error": "Failed to convert PDF to images", "success": False}

        # Step 2: Run OCR on each page
        page_texts = []
        for i, image in enumerate(images):
            text = tesseract_engine.extract_text_from_pil_image(image)
            if text:
                page_texts.append(f"--- Page {i + 1} ---\n{text}")

        if not page_texts:
            return {"error": "OCR produced no text from PDF", "success": False}

        raw_text = "\n\n".join(page_texts)
        logger.info(f"OCR extracted {len(raw_text)} total characters from {len(images)} pages")

        # Step 3: LLM structured extraction
        extracted_data = await structured_extractor.extract_quotation_data(raw_text)

        if extracted_data is None:
            return {
                "success": True,
                "raw_text": raw_text,
                "extracted_data": None,
                "extraction_failed": True,
                "pages_processed": len(images),
            }

        # Step 4: Validate extraction
        validated = await structured_extractor.validate_extraction(extracted_data)

        return {
            "success": True,
            "raw_text": raw_text,
            "extracted_data": validated,
            "extraction_failed": False,
            "pages_processed": len(images),
            "confidence": validated.get("_validation", {}).get("confidence", 0),
        }

    async def process_image(self, image_path: str) -> dict:
        """Process a single image file (JPG/PNG) through OCR + extraction."""
        path = Path(image_path)
        if not path.exists():
            return {"error": f"File not found: {image_path}", "success": False}

        raw_text = tesseract_engine.extract_text_from_image(image_path)
        if not raw_text:
            return {"error": "OCR produced no text", "success": False}

        extracted_data = await structured_extractor.extract_quotation_data(raw_text)

        if extracted_data:
            validated = await structured_extractor.validate_extraction(extracted_data)
        else:
            validated = None

        return {
            "success": True,
            "raw_text": raw_text,
            "extracted_data": validated,
            "extraction_failed": validated is None,
            "pages_processed": 1,
        }

    async def process_attachment(self, file_path: str, file_type: str) -> dict:
        """
        Route attachment processing based on file type.
        """
        if file_type in ("pdf",):
            return await self.process_pdf(file_path)
        elif file_type in ("jpg", "jpeg", "png", "tiff", "bmp"):
            return await self.process_image(file_path)
        else:
            return {
                "success": False,
                "error": f"Unsupported file type for OCR: {file_type}",
            }


ocr_pipeline = OCRPipeline()
