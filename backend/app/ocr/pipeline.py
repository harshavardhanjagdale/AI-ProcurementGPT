"""
OCR Pipeline - Combines PDF text extraction, Tesseract OCR fallback,
and LLM extraction into a single end-to-end processing flow.
"""
import logging
from pathlib import Path

import pdfplumber

from app.ocr.pdf_converter import pdf_converter
from app.ocr.tesseract_engine import tesseract_engine
from app.ocr.structured_extractor import structured_extractor

logger = logging.getLogger(__name__)

MIN_CHARS_FOR_GOOD_EXTRACTION = 50


class OCRPipeline:
    """
    Full OCR pipeline:
    1. Try direct text extraction from PDF (pdfplumber) — perfect for digital PDFs
    2. Fall back to image-based Tesseract OCR — for scanned documents
    3. Use LLM to extract structured quotation data from the text
    """

    def _extract_text_direct(self, pdf_path: str) -> str | None:
        """Extract text directly from a digital PDF using pdfplumber.

        Returns the combined text if meaningful content is found, None otherwise.
        """
        try:
            page_texts = []
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    tables = page.extract_tables() or []

                    parts = []
                    if text.strip():
                        parts.append(text)

                    for table in tables:
                        rows = []
                        for row in table:
                            cells = [str(cell) if cell is not None else "" for cell in row]
                            rows.append(" | ".join(cells))
                        if rows:
                            parts.append("\n".join(rows))

                    combined = "\n".join(parts).strip()
                    if combined:
                        page_texts.append(f"--- Page {i + 1} ---\n{combined}")

            if not page_texts:
                return None

            full_text = "\n\n".join(page_texts)
            if len(full_text.strip()) < MIN_CHARS_FOR_GOOD_EXTRACTION:
                return None

            return full_text

        except Exception as e:
            logger.warning(f"[OCR] pdfplumber extraction failed: {e} — will fall back to Tesseract")
            return None

    def _extract_text_tesseract(self, pdf_path: str) -> str | None:
        """Fall back to image-based Tesseract OCR for scanned PDFs."""
        images = pdf_converter.pdf_to_images(pdf_path)
        if not images:
            return None

        page_texts = []
        for i, image in enumerate(images):
            text = tesseract_engine.extract_text_from_pil_image(image)
            if text:
                page_texts.append(f"--- Page {i + 1} ---\n{text}")

        if not page_texts:
            return None

        return "\n\n".join(page_texts)

    async def process_pdf(self, pdf_path: str, rfq_items: list[dict] | None = None) -> dict:
        """
        Process a PDF file through the full pipeline.

        Returns:
            dict with raw_text, extracted_data, and metadata
        """
        path = Path(pdf_path)
        if not path.exists():
            return {"error": f"File not found: {pdf_path}", "success": False}

        logger.info(f"[OCR] Starting pipeline for: {pdf_path}")

        # Step 1: Try direct text extraction (digital PDF)
        raw_text = self._extract_text_direct(pdf_path)
        extraction_method = "pdfplumber"

        # Step 2: Fall back to Tesseract if direct extraction yielded nothing useful
        if raw_text is None:
            logger.info("[OCR] Direct extraction insufficient — falling back to Tesseract")
            raw_text = self._extract_text_tesseract(pdf_path)
            extraction_method = "tesseract"

        if not raw_text:
            return {"error": "Could not extract text from PDF", "success": False}

        logger.info(f"[OCR] Extracted {len(raw_text)} chars via {extraction_method}")

        # Step 3: LLM structured extraction
        extracted_data = await structured_extractor.extract_quotation_data(raw_text, rfq_items=rfq_items)

        if extracted_data is None:
            return {
                "success": True,
                "raw_text": raw_text,
                "extracted_data": None,
                "extraction_failed": True,
                "extraction_method": extraction_method,
                "pages_processed": raw_text.count("--- Page "),
            }

        # Step 4: Validate extraction
        validated = await structured_extractor.validate_extraction(extracted_data)

        return {
            "success": True,
            "raw_text": raw_text,
            "extracted_data": validated,
            "extraction_failed": False,
            "extraction_method": extraction_method,
            "pages_processed": raw_text.count("--- Page "),
            "confidence": validated.get("_validation", {}).get("confidence", 0),
        }

    async def process_image(self, image_path: str, rfq_items: list[dict] | None = None) -> dict:
        """Process a single image file (JPG/PNG) through OCR + extraction."""
        path = Path(image_path)
        if not path.exists():
            return {"error": f"File not found: {image_path}", "success": False}

        raw_text = tesseract_engine.extract_text_from_image(image_path)
        if not raw_text:
            return {"error": "OCR produced no text", "success": False}

        extracted_data = await structured_extractor.extract_quotation_data(raw_text, rfq_items=rfq_items)

        if extracted_data:
            validated = await structured_extractor.validate_extraction(extracted_data)
        else:
            validated = None

        return {
            "success": True,
            "raw_text": raw_text,
            "extracted_data": validated,
            "extraction_failed": validated is None,
            "extraction_method": "tesseract",
            "pages_processed": 1,
        }

    async def process_attachment(self, file_path: str, file_type: str, rfq_items: list[dict] | None = None) -> dict:
        """
        Route attachment processing based on file type.
        """
        if file_type in ("pdf",):
            return await self.process_pdf(file_path, rfq_items=rfq_items)
        elif file_type in ("jpg", "jpeg", "png", "tiff", "bmp"):
            return await self.process_image(file_path, rfq_items=rfq_items)
        else:
            return {
                "success": False,
                "error": f"Unsupported file type for OCR: {file_type}",
            }


ocr_pipeline = OCRPipeline()
