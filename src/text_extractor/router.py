"""Smart router: detect document type and pick the best extraction backend.

Strategy (quality-aware fallback chain):
1. Image file → Tesseract OCR (if available)
2. PDF → try pypdf (fast) → check quality → pdfplumber → docling → pdf2image+OCR
3. Each step checks text quality; escalates if garbled or empty.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from text_extractor.backends import tesseract_backend
from text_extractor.backends.pypdf_backend import extract as pypdf_extract
from text_extractor.backends.pypdf_backend import extract_pages as pypdf_extract_pages
from text_extractor.quality import is_low_quality, text_quality_score
from text_extractor.types import ExtractionResult

logger = logging.getLogger(__name__)


def _is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def _pdf_has_text(file_path: Path) -> bool:
    """Quick check: does the PDF have any extractable text?"""
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        for page in reader.pages[:3]:
            text = page.extract_text() or ""
            if text.strip():
                return True
        return False
    except Exception:
        return False


def _sample_text(result: ExtractionResult, sample_pages: int = 5) -> str:
    """Get sample text from the middle pages (where real content usually is)."""
    if not result.pages:
        return ""
    # Sample from ~20% into the doc onward (skip frontmatter)
    start = max(0, len(result.pages) // 5)
    end = min(start + sample_pages, len(result.pages))
    return "\n".join(p.text for p in result.pages[start:end] if p.text.strip())


def _quick_pdf_health(file_path: Path) -> tuple[float, float]:
    """Quickly estimate (quality_score, meaningful_chars_per_sampled_page).

    Samples a handful of pages instead of extracting full document to reduce latency.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        total = len(reader.pages)
        if total == 0:
            return 0.0, 0.0

        idx = sorted({0, min(1, total - 1), total // 2, max(total - 2, 0), total - 1})
        texts: list[str] = []
        meaningful_total = 0

        for i in idx:
            t = reader.pages[i].extract_text() or ""
            texts.append(t)
            meaningful_total += sum(1 for c in t if c.isalnum())

        joined = "\n".join(texts)
        score = text_quality_score(joined)
        density = meaningful_total / max(1, len(idx))
        return score, density
    except Exception:
        return 0.0, 0.0


def detect_strategy(file_path: str | Path) -> str:
    """Detect which extraction strategy to use.

    Returns one of: "pypdf", "pdfplumber", "docling", "pdf2image_ocr",
    "tesseract_image", "tesseract_pdf", "pypdf_fallback", "unsupported"
    """
    path = Path(file_path)

    if tesseract_backend.is_image_file(path):
        if tesseract_backend.is_available():
            return "tesseract_image"
        return "unsupported"

    if _is_pdf(path):
        # For very large PDFs, skip expensive full-text backends by default.
        # These are often scanned/image-heavy exam books.
        try:
            size_mb = path.stat().st_size / (1024 * 1024)
        except OSError:
            size_mb = 0.0

        if size_mb >= 20:
            from text_extractor.backends import pdf2image_backend
            if pdf2image_backend.is_available():
                return "pdf2image_ocr"
            if tesseract_backend.is_available():
                return "tesseract_pdf"
            return "pypdf_fallback"

        quick_score, quick_density = _quick_pdf_health(path)

        # If sampled pages have very low meaningful content, this is likely
        # an image PDF with sparse text layer. Prefer OCR immediately.
        if quick_density < 120:
            from text_extractor.backends import pdf2image_backend
            if pdf2image_backend.is_available():
                return "pdf2image_ocr"
            if tesseract_backend.is_available():
                return "tesseract_pdf"
            return "pypdf_fallback"

        if not _pdf_has_text(path):
            # No text at all — need OCR
            from text_extractor.backends import pdf2image_backend
            if pdf2image_backend.is_available():
                return "pdf2image_ocr"
            if tesseract_backend.is_available():
                return "tesseract_pdf"
            return "pypdf_fallback"
        # Has text — quality determined at extraction time
        # But if quick sample already looks garbled, prefer pdfplumber.
        if quick_score < 0.85:
            from text_extractor.backends import pdfplumber_backend
            from text_extractor.backends import docling_backend
            if not pdfplumber_backend.is_available() and docling_backend.is_available():
                return "docling"
            return "pdfplumber"
        return "pypdf"

    return "unsupported"


def extract(
    file_path: str | Path,
    start_page: int | None = None,
    end_page: int | None = None,
) -> ExtractionResult:
    """Route extraction with quality-aware fallback chain.

    Chain: pypdf → pdfplumber → docling → pdf2image+OCR
    At each step, sample text quality. If low, escalate.
    """
    path = Path(file_path)

    if not path.exists():
        return ExtractionResult(
            source=str(path),
            error=f"File not found: {path}",
        )

    strategy = detect_strategy(path)
    t0 = time.perf_counter()
    logger.info("File: %s → initial strategy: %s", path.name, strategy)

    # Image files — direct to OCR
    if strategy == "tesseract_image":
        result = tesseract_backend.extract_image(path)
        _log_timing(result, t0)
        return result

    # No-text PDFs — direct to OCR
    if strategy in ("pdf2image_ocr", "tesseract_pdf"):
        result = _extract_ocr(path, strategy, start_page=start_page, end_page=end_page)
        _log_timing(result, t0)
        return result

    if strategy == "unsupported":
        return ExtractionResult(
            source=str(path),
            error=f"Unsupported file type: {path.suffix}. "
            "Supported: .pdf, .png, .jpg, .jpeg, .gif, .bmp, .tiff, .tif, .webp",
        )

    # Text PDFs — quality-aware selection
    if strategy == "docling":
        from text_extractor.backends import docling_backend
        if start_page is not None or end_page is not None:
            result = docling_backend.extract_pages(path, start_page or 1, end_page or 10**9)
        else:
            result = docling_backend.extract(path)
    elif strategy == "pdfplumber":
        from text_extractor.backends import pdfplumber_backend
        if pdfplumber_backend.is_available():
            if start_page is not None or end_page is not None:
                result = pdfplumber_backend.extract_pages(path, start_page or 1, end_page or 10**9)
            else:
                result = pdfplumber_backend.extract(path)
        else:
            if start_page is not None or end_page is not None:
                result = pypdf_extract_pages(path, start_page or 1, end_page or 10**9)
            else:
                result = pypdf_extract(path)
    else:
        # Step 1: pypdf (fastest)
        if start_page is not None or end_page is not None:
            result = pypdf_extract_pages(path, start_page or 1, end_page or 10**9)
        else:
            result = pypdf_extract(path)

    sample = _sample_text(result)
    score = text_quality_score(sample)
    density = sum(1 for c in sample if c.isalnum()) / max(1, min(5, len(result.pages)))
    logger.info("pypdf quality score: %.2f", score)

    if score >= 0.85 and density >= 120 and not is_low_quality(sample, page_count=1):
        _log_timing(result, t0)
        return result

    # Step 2: pdfplumber (better font decoding)
    from text_extractor.backends import pdfplumber_backend
    if pdfplumber_backend.is_available():
        logger.info("Quality low (%.2f), trying pdfplumber...", score)
        if start_page is not None or end_page is not None:
            plumber_result = pdfplumber_backend.extract_pages(path, start_page or 1, end_page or 10**9)
        else:
            plumber_result = pdfplumber_backend.extract(path)
        plumber_sample = _sample_text(plumber_result)
        plumber_score = text_quality_score(plumber_sample)
        logger.info("pdfplumber quality score: %.2f", plumber_score)

        if plumber_score >= 0.85:
            _log_timing(plumber_result, t0)
            return plumber_result

        # Keep the better one
        if plumber_score > score:
            result = plumber_result
            score = plumber_score

    # Step 3: docling (optional high-quality parser)
    from text_extractor.backends import docling_backend
    if (score < 0.85 or density < 120) and docling_backend.is_available():
        logger.info("Quality still low (%.2f), trying docling...", score)
        if start_page is not None or end_page is not None:
            docling_result = docling_backend.extract_pages(path, start_page or 1, end_page or 10**9)
        else:
            docling_result = docling_backend.extract(path)
        docling_sample = _sample_text(docling_result)
        docling_score = text_quality_score(docling_sample)
        logger.info("docling quality score: %.2f", docling_score)

        if docling_score > score:
            result = docling_result
            score = docling_score

    # Step 4: pdf2image + OCR (last resort for PDFs)
    from text_extractor.backends import pdf2image_backend
    if (score < 0.85 or density < 120) and pdf2image_backend.is_available():
        logger.info("Quality still low (%.2f), trying pdf2image+OCR...", score)
        ocr_result = pdf2image_backend.extract(
            path,
            start_page=start_page,
            end_page=end_page,
        )
        ocr_sample = _sample_text(ocr_result)
        ocr_score = text_quality_score(ocr_sample)
        logger.info("pdf2image+OCR quality score: %.2f", ocr_score)

        if ocr_score > score:
            result = ocr_result

    if strategy == "pypdf_fallback":
        logger.warning(
            "PDF appears scanned but no OCR backend available. "
            "Install tesseract-ocr + poppler and pip install text-extractor[ocr] for OCR."
        )

    _log_timing(result, t0)
    return result


def _extract_ocr(
    path: Path,
    strategy: str,
    start_page: int | None = None,
    end_page: int | None = None,
) -> ExtractionResult:
    """Extract via OCR backend."""
    if strategy == "pdf2image_ocr":
        from text_extractor.backends import pdf2image_backend
        return pdf2image_backend.extract(path, start_page=start_page, end_page=end_page)
    return tesseract_backend.extract_scanned_pdf(path, start_page=start_page, end_page=end_page)


def _log_timing(result: ExtractionResult, t0: float) -> None:
    elapsed = time.perf_counter() - t0
    logger.info(
        "Extraction done: %s, %d pages, %d chars, %.1fs [%s]",
        result.source, result.total_pages, result.total_chars,
        elapsed, result.backend_used,
    )
