"""Smart router: detect document type and pick the best extraction backend.

Strategy (quality-aware fallback chain):
1. Image file → Tesseract OCR (if available)
2. PDF → preflight with PyMuPDF (or pypdf) to measure text density and quality
3. Sparse/scanned PDF → pdf2image+OCR
4. Dense digital PDF → pymupdf (preferred) → pdfplumber → docling → OCR
   Each step checks quality (including CID artifact detection); escalates if poor.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from text_extractor.backends import tesseract_backend
from text_extractor.backends.pypdf_backend import extract as pypdf_extract
from text_extractor.backends.pypdf_backend import extract_pages as pypdf_extract_pages
from text_extractor.quality import cid_ratio, is_low_quality, text_quality_score
from text_extractor.types import ExtractionResult

logger = logging.getLogger(__name__)


def _is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


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

    Samples pages at 0%, 25%, 50%, 75% of the document to avoid bias from
    cover/promotional last pages.  Prefers PyMuPDF for sampling when available
    because it is faster and handles font encoding correctly.
    """
    try:
        try:
            import fitz
            return _quick_health_fitz(file_path, fitz)
        except ImportError:
            return _quick_health_pypdf(file_path)
    except Exception:
        return 0.0, 0.0


def _quick_health_fitz(file_path: Path, fitz) -> tuple[float, float]:  # type: ignore[type-arg]
    doc = fitz.open(str(file_path))
    try:
        total = len(doc)
        if total == 0:
            return 0.0, 0.0
        # Sample at 0%, 25%, 50%, 75% (skip last page to avoid promotional footers)
        idx = sorted({int(total * q) for q in (0.0, 0.25, 0.5, 0.75)})
        idx = [max(0, min(i, total - 1)) for i in idx]
        texts: list[str] = []
        meaningful_total = 0
        for i in idx:
            t = doc[i].get_text()
            texts.append(t)
            meaningful_total += sum(1 for c in t if c.isalnum())
        joined = "\n".join(texts)
        score = text_quality_score(joined)
        density = meaningful_total / max(1, len(idx))
        return score, density
    finally:
        doc.close()


def _quick_health_pypdf(file_path: Path) -> tuple[float, float]:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    total = len(reader.pages)
    if total == 0:
        return 0.0, 0.0
    idx = sorted({int(total * q) for q in (0.0, 0.25, 0.5, 0.75)})
    idx = [max(0, min(i, total - 1)) for i in idx]
    texts: list[str] = []
    meaningful_total = 0
    for i in idx:
        t = reader.pages[i].extract_text() or ""
        texts.append(t)
        # Strip CID patterns before counting meaningful chars so that CID-heavy
        # pages don't look falsely dense.
        from text_extractor.quality import _CID_PATTERN  # type: ignore[attr-defined]
        clean_t = _CID_PATTERN.sub("", t)
        meaningful_total += sum(1 for c in clean_t if c.isalnum())
    joined = "\n".join(texts)
    score = text_quality_score(joined)
    density = meaningful_total / max(1, len(idx))
    return score, density


def detect_strategy(file_path: str | Path) -> str:
    """Detect which extraction strategy to use.

    Returns one of: "pymupdf", "pypdf", "pdfplumber", "docling",
    "pdf2image_ocr", "tesseract_image", "tesseract_pdf",
    "pypdf_fallback", "unsupported"
    """
    path = Path(file_path)

    if tesseract_backend.is_image_file(path):
        if tesseract_backend.is_available():
            return "tesseract_image"
        return "unsupported"

    if _is_pdf(path):
        # Preflight: sample a few pages to assess text density and quality.
        # Uses PyMuPDF if available (faster + correct font decoding);
        # falls back to pypdf otherwise.
        quick_score, quick_density = _quick_pdf_health(path)

        # Sparse text layer — likely a scanned/image PDF.  Route to OCR.
        if quick_density < 120:
            from text_extractor.backends import pdf2image_backend
            if pdf2image_backend.is_available():
                return "pdf2image_ocr"
            if tesseract_backend.is_available():
                return "tesseract_pdf"
            return "pypdf_fallback"

        # Dense text found.  Prefer pymupdf when available; it is fast and
        # handles custom font encodings that trip up pypdf/pdfplumber.
        from text_extractor.backends import pymupdf_backend
        if pymupdf_backend.is_available():
            return "pymupdf"

        # pymupdf not installed — fall back to pypdf / pdfplumber.
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

    # ── Text PDFs: quality-aware extraction chain ─────────────────────────────
    #
    # Preferred order (when pymupdf installed):
    #   pymupdf → (quality check) → pdfplumber → docling → OCR
    #
    # When pymupdf is absent:
    #   pypdf → pdfplumber → docling → OCR
    #
    # "docling" and "pdfplumber" strategy values are direct routes when
    # detect_strategy() already determined the right starting backend.
    # ─────────────────────────────────────────────────────────────────────────

    if strategy == "docling":
        from text_extractor.backends import docling_backend
        if start_page is not None or end_page is not None:
            # Docling does not honour page ranges — fall back to a page-aware backend.
            from text_extractor.backends import pdfplumber_backend
            if pdfplumber_backend.is_available():
                result = pdfplumber_backend.extract_pages(path, start_page or 1, end_page or 10**9)
            else:
                result = pypdf_extract_pages(path, start_page or 1, end_page or 10**9)
        elif docling_backend.is_available():
            try:
                result = docling_backend.extract(path)
            except Exception:
                logger.exception("Docling extraction failed; falling back to pypdf.")
                result = pypdf_extract(path)
        else:
            result = pypdf_extract(path)

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

    elif strategy == "pymupdf":
        # Step 1 (preferred): PyMuPDF — fast and handles custom font encodings.
        from text_extractor.backends import pymupdf_backend
        if start_page is not None or end_page is not None:
            result = pymupdf_backend.extract_pages(path, start_page or 1, end_page or 10**9)
        else:
            result = pymupdf_backend.extract(path)

    else:
        # strategy == "pypdf" or "pypdf_fallback"
        if start_page is not None or end_page is not None:
            result = pypdf_extract_pages(path, start_page or 1, end_page or 10**9)
        else:
            result = pypdf_extract(path)

    sample = _sample_text(result)
    score = text_quality_score(sample)
    density = sum(1 for c in sample if c.isalnum()) / max(1, min(5, len(result.pages)))
    logger.info("%s quality score: %.2f  density: %.0f", strategy, score, density)

    if score >= 0.85 and density >= 120 and not is_low_quality(sample, page_count=1):
        _log_timing(result, t0)
        return result

    # Step 2: pdfplumber — better font decoding than pypdf.
    # Skip if we already tried it above (strategy == "pdfplumber").
    from text_extractor.backends import pdfplumber_backend
    if strategy not in ("pdfplumber", "docling") and pdfplumber_backend.is_available():
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

        if plumber_score > score:
            result = plumber_result
            score = plumber_score

    # Step 3: docling (optional heavy parser).
    from text_extractor.backends import docling_backend
    if (
        start_page is None
        and end_page is None
        and score < 0.85
        and strategy not in ("docling",)
        and docling_backend.is_available()
    ):
        logger.info("Quality still low (%.2f), trying docling...", score)
        try:
            docling_result = docling_backend.extract(path)
            docling_sample = _sample_text(docling_result)
            docling_score = text_quality_score(docling_sample)
            logger.info("docling quality score: %.2f", docling_score)
            if docling_score > score:
                result = docling_result
                score = docling_score
        except Exception:
            logger.exception("Docling extraction failed; continuing to OCR fallback.")

    # Step 4: pdf2image + OCR (last resort).
    from text_extractor.backends import pdf2image_backend
    if score < 0.85 and pdf2image_backend.is_available():
        logger.info("Quality still low (%.2f), trying pdf2image+OCR...", score)
        ocr_result = pdf2image_backend.extract(path, start_page=start_page, end_page=end_page)
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
