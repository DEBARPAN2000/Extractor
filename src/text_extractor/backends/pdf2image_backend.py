"""pdf2image + OCR backend: convert PDF pages to images then OCR.

Handles image-based PDFs (CorelDRAW, scanned) and PDFs with custom font encoding
where text extraction fails. Uses poppler's pdftoppm for page rendering.

Requires: pdf2image, Pillow, pytesseract (and system deps: poppler-utils, tesseract-ocr)
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from text_extractor.system_bins import find_poppler_bin, find_tesseract
from text_extractor.types import ExtractionResult, PageResult

BACKEND_NAME = "pdf2image_ocr"
logger = logging.getLogger(__name__)

# DPI for rendering — 200 is good balance of speed vs quality
DEFAULT_DPI = 150
MAX_WORKERS = max(2, min(8, (os.cpu_count() or 4)))


def _ocr_single_page(args: tuple) -> PageResult:
    """OCR a single page image. Designed for ThreadPoolExecutor."""
    import pytesseract

    page_num, image = args
    tesseract_path = find_tesseract()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

    # psm 6: assume a block of text; good speed/quality tradeoff for exam PDFs.
    text = pytesseract.image_to_string(image, config="--oem 1 --psm 6").strip()
    return PageResult(
        page_number=page_num,
        text=text,
        has_images=True,
        is_scanned=True,
    )


def extract(
    file_path: str | Path,
    *,
    dpi: int = DEFAULT_DPI,
    start_page: int | None = None,
    end_page: int | None = None,
    max_workers: int = MAX_WORKERS,
) -> ExtractionResult:
    """Extract text from a PDF by rendering to images + OCR.

    Args:
        file_path: Path to PDF.
        dpi: Resolution for rendering. Higher = better OCR but slower.
        start_page: First page (1-indexed). None = first page.
        end_page: Last page (1-indexed, inclusive). None = last page.
        max_workers: Thread pool size for parallel OCR.
    """
    from pdf2image import convert_from_path

    path = Path(file_path)

    kwargs: dict = {
        "dpi": dpi,
        "grayscale": True,
        "fmt": "jpeg",
        "thread_count": max(1, min(4, max_workers)),
    }
    poppler_bin = find_poppler_bin()
    if poppler_bin:
        kwargs["poppler_path"] = poppler_bin

    if start_page is not None:
        kwargs["first_page"] = start_page
    if end_page is not None:
        kwargs["last_page"] = end_page

    logger.info("Rendering %s at %d DPI...", path.name, dpi)
    images = convert_from_path(str(path), **kwargs)

    first_page_num = start_page or 1

    # Parallel OCR across pages
    page_args = [(first_page_num + i, img) for i, img in enumerate(images)]
    pages: list[PageResult] = []

    if len(images) > 1 and max_workers > 1:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(images))) as pool:
            futures = {pool.submit(_ocr_single_page, a): a[0] for a in page_args}
            for future in as_completed(futures):
                try:
                    pages.append(future.result())
                except Exception as e:
                    pn = futures[future]
                    logger.warning("OCR failed for page %d: %s", pn, e)
                    pages.append(PageResult(page_number=pn, text="", is_scanned=True))
    else:
        for args in page_args:
            try:
                pages.append(_ocr_single_page(args))
            except Exception as e:
                logger.warning("OCR failed for page %d: %s", args[0], e)
                pages.append(PageResult(page_number=args[0], text="", is_scanned=True))

    # Sort by page number (futures may complete out of order)
    pages.sort(key=lambda p: p.page_number)

    # Get total page count from the PDF
    from pypdf import PdfReader
    total = len(PdfReader(path).pages)

    return ExtractionResult(
        source=str(path),
        pages=pages,
        total_pages=total,
        backend_used=BACKEND_NAME,
    )


def is_available() -> bool:
    """Check if pdf2image + tesseract are available."""
    try:
        import pytesseract
        from pdf2image import convert_from_path  # noqa: F401
        from PIL import Image  # noqa: F401

        tesseract_path = find_tesseract()
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

        pytesseract.get_tesseract_version()
        return find_poppler_bin() is not None
    except Exception:
        return False
