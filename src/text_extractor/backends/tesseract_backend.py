"""OCR backend: Tesseract for scanned PDFs and images.

Requires optional deps: pytesseract, Pillow
Requires system dep: tesseract-ocr
Install: pip install text-extractor[ocr]
"""

from __future__ import annotations

import logging
from pathlib import Path

from text_extractor.system_bins import find_tesseract
from text_extractor.types import ExtractionResult, PageResult

BACKEND_NAME = "tesseract"
logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


def _ocr_image(image) -> str:
    """Run Tesseract OCR on a PIL Image."""
    import pytesseract

    tesseract_path = find_tesseract()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

    return pytesseract.image_to_string(image).strip()


def extract_image(file_path: str | Path) -> ExtractionResult:
    """Extract text from an image file via OCR."""
    from PIL import Image

    path = Path(file_path)
    img = Image.open(path)
    text = _ocr_image(img)

    return ExtractionResult(
        source=str(path),
        pages=[PageResult(page_number=1, text=text, is_scanned=True)],
        total_pages=1,
        backend_used=BACKEND_NAME,
    )


def extract_scanned_pdf(
    file_path: str | Path,
    start_page: int | None = None,
    end_page: int | None = None,
) -> ExtractionResult:
    """Extract text from a scanned PDF by OCRing embedded page images."""
    from PIL import Image
    from pypdf import PdfReader

    path = Path(file_path)
    reader = PdfReader(path)
    pages: list[PageResult] = []

    total = len(reader.pages)
    start = max(1, start_page or 1)
    end = min(end_page or total, total)

    for i in range(start - 1, end):
        page = reader.pages[i]
        page_text_parts: list[str] = []

        # Try to extract images from the page and OCR them
        if hasattr(page, "images") and page.images:
            for img_obj in page.images:
                try:
                    from io import BytesIO

                    img = Image.open(BytesIO(img_obj.data))
                    ocr_text = _ocr_image(img)
                    if ocr_text:
                        page_text_parts.append(ocr_text)
                except Exception as e:
                    logger.debug("Failed to OCR image on page %d: %s", i + 1, e)

        text = "\n".join(page_text_parts)
        pages.append(
            PageResult(
                page_number=i + 1,
                text=text,
                has_images=True,
                is_scanned=True,
            )
        )

    return ExtractionResult(
        source=str(path),
        pages=pages,
        total_pages=total,
        backend_used=BACKEND_NAME,
    )


def is_available() -> bool:
    """Check if Tesseract OCR is available."""
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401

        tesseract_path = find_tesseract()
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

        # Verify tesseract binary is installed
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def is_image_file(file_path: str | Path) -> bool:
    """Check if a file is a supported image format."""
    return Path(file_path).suffix.lower() in _IMAGE_EXTENSIONS
