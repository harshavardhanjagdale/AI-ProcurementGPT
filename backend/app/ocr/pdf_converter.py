"""
Converts PDF files to images for OCR processing.
Uses pdf2image (requires poppler installed on system).
"""
import logging
from pathlib import Path

from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)


class PDFConverter:
    def __init__(self, dpi: int = 300):
        self.dpi = dpi

    def pdf_to_images(self, pdf_path: str) -> list[Image.Image]:
        """
        Convert PDF pages to PIL Image objects.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of PIL Images (one per page)
        """
        path = Path(pdf_path)
        if not path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return []

        if path.suffix.lower() != ".pdf":
            logger.warning(f"File is not a PDF: {pdf_path}")
            return []

        try:
            images = convert_from_path(
                str(path),
                dpi=self.dpi,
                fmt="png",
            )
            logger.info(f"Converted PDF to {len(images)} images: {pdf_path}")
            return images
        except Exception as e:
            logger.error(f"PDF conversion failed for {pdf_path}: {e}")
            return []

    def pdf_to_image_files(self, pdf_path: str, output_dir: str | None = None) -> list[str]:
        """
        Convert PDF to image files saved on disk.

        Returns:
            List of saved image file paths
        """
        images = self.pdf_to_images(pdf_path)
        if not images:
            return []

        if output_dir is None:
            output_dir = str(Path(pdf_path).parent)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        pdf_stem = Path(pdf_path).stem
        saved_paths = []

        for i, image in enumerate(images):
            img_path = output_path / f"{pdf_stem}_page_{i + 1}.png"
            image.save(str(img_path), "PNG")
            saved_paths.append(str(img_path))

        logger.info(f"Saved {len(saved_paths)} page images to {output_dir}")
        return saved_paths


pdf_converter = PDFConverter()
