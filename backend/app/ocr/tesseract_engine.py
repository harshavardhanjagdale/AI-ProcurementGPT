"""
Tesseract OCR engine wrapper.
Extracts text from images and PDFs using pytesseract.
"""
import logging
from pathlib import Path

import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)


class TesseractEngine:
    def __init__(self, lang: str = "eng", config: str = ""):
        self.lang = lang
        self.config = config or "--oem 3 --psm 6"

    def extract_text_from_image(self, image_path: str) -> str:
        """Extract text from a single image file."""
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang=self.lang, config=self.config)
            logger.info(f"OCR extracted {len(text)} chars from {image_path}")
            return text.strip()
        except Exception as e:
            logger.error(f"OCR failed for image {image_path}: {e}")
            return ""

    def extract_text_from_pil_image(self, image: Image.Image) -> str:
        """Extract text from a PIL Image object."""
        try:
            text = pytesseract.image_to_string(image, lang=self.lang, config=self.config)
            return text.strip()
        except Exception as e:
            logger.error(f"OCR failed for PIL image: {e}")
            return ""

    def extract_with_confidence(self, image_path: str) -> dict:
        """Extract text with confidence data for each word."""
        try:
            image = Image.open(image_path)
            data = pytesseract.image_to_data(
                image, lang=self.lang, config=self.config, output_type=pytesseract.Output.DICT
            )

            words = []
            for i, text in enumerate(data["text"]):
                if text.strip():
                    words.append({
                        "text": text,
                        "confidence": data["conf"][i],
                        "left": data["left"][i],
                        "top": data["top"][i],
                        "width": data["width"][i],
                        "height": data["height"][i],
                    })

            full_text = " ".join(w["text"] for w in words)
            avg_confidence = (
                sum(w["confidence"] for w in words) / len(words) if words else 0
            )

            return {
                "text": full_text,
                "words": words,
                "avg_confidence": avg_confidence,
                "word_count": len(words),
            }
        except Exception as e:
            logger.error(f"OCR confidence extraction failed: {e}")
            return {"text": "", "words": [], "avg_confidence": 0, "word_count": 0}


tesseract_engine = TesseractEngine()
