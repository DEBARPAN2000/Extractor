"""Tests for the smart router."""

from pathlib import Path
from unittest.mock import patch

from text_extractor.router import detect_strategy, extract
from text_extractor.types import ExtractionResult, PageResult


def test_detect_unsupported_file():
    # .docx is not supported
    assert detect_strategy("file.docx") == "unsupported"


def test_detect_image_without_tesseract():
    with patch("text_extractor.backends.tesseract_backend.is_available", return_value=False):
        assert detect_strategy("photo.png") == "unsupported"


def test_detect_image_with_tesseract():
    with patch("text_extractor.backends.tesseract_backend.is_available", return_value=True):
        assert detect_strategy("photo.jpg") == "tesseract_image"


def test_extract_missing_file():
    result = extract("nonexistent.pdf")
    assert result.error is not None
    assert "not found" in result.error.lower()


def test_detect_pdf_docling_when_pdfplumber_unavailable():
    with patch("text_extractor.router._quick_pdf_health", return_value=(0.6, 200)):
        with patch("text_extractor.router._pdf_has_text", return_value=True):
            with patch("text_extractor.backends.pdfplumber_backend.is_available", return_value=False):
                with patch("text_extractor.backends.docling_backend.is_available", return_value=True):
                    assert detect_strategy("complex.pdf") == "docling"


def test_extract_attempts_docling_when_quality_is_low(tmp_path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    pypdf_result = ExtractionResult(
        source=str(pdf),
        pages=[PageResult(page_number=1, text="x")],
        total_pages=1,
        backend_used="pypdf",
    )
    docling_result = ExtractionResult(
        source=str(pdf),
        pages=[PageResult(page_number=1, text="clear content")],
        total_pages=1,
        backend_used="docling",
    )

    with patch("text_extractor.router.detect_strategy", return_value="pypdf"):
        with patch("text_extractor.router.pypdf_extract", return_value=pypdf_result):
            with patch("text_extractor.backends.pdfplumber_backend.is_available", return_value=False):
                with patch("text_extractor.backends.docling_backend.is_available", return_value=True):
                    with patch("text_extractor.backends.docling_backend.extract", return_value=docling_result) as mock_docling:
                        with patch("text_extractor.backends.pdf2image_backend.is_available", return_value=False):
                            with patch("text_extractor.router.text_quality_score", side_effect=[0.2, 0.95]):
                                with patch("text_extractor.router.is_low_quality", return_value=True):
                                    result = extract(pdf)

    assert mock_docling.called
    assert result.backend_used == "docling"


def test_extract_docling_failure_does_not_abort(tmp_path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    pypdf_result = ExtractionResult(
        source=str(pdf),
        pages=[PageResult(page_number=1, text="x")],
        total_pages=1,
        backend_used="pypdf",
    )

    with patch("text_extractor.router.detect_strategy", return_value="pypdf"):
        with patch("text_extractor.router.pypdf_extract", return_value=pypdf_result):
            with patch("text_extractor.backends.pdfplumber_backend.is_available", return_value=False):
                with patch("text_extractor.backends.docling_backend.is_available", return_value=True):
                    with patch("text_extractor.backends.docling_backend.extract", side_effect=RuntimeError("boom")):
                        with patch("text_extractor.backends.pdf2image_backend.is_available", return_value=False):
                            with patch("text_extractor.router.text_quality_score", return_value=0.2):
                                with patch("text_extractor.router.is_low_quality", return_value=True):
                                    result = extract(pdf)

    assert result.backend_used == "pypdf"
    assert result.error is None


def test_extract_skips_docling_when_page_range_requested(tmp_path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    ranged_result = ExtractionResult(
        source=str(pdf),
        pages=[
            PageResult(page_number=2, text="page 2"),
            PageResult(page_number=3, text="page 3"),
        ],
        total_pages=2,
        backend_used="pypdf",
    )

    with patch("text_extractor.router.detect_strategy", return_value="pypdf"):
        with patch("text_extractor.router.pypdf_extract_pages", return_value=ranged_result):
            with patch("text_extractor.backends.pdfplumber_backend.is_available", return_value=False):
                with patch("text_extractor.backends.docling_backend.is_available", return_value=True):
                    with patch("text_extractor.backends.docling_backend.extract") as mock_docling_extract:
                        with patch("text_extractor.backends.pdf2image_backend.is_available", return_value=False):
                            with patch("text_extractor.router.text_quality_score", return_value=0.2):
                                with patch("text_extractor.router.is_low_quality", return_value=True):
                                    result = extract(pdf, start_page=2, end_page=3)

    assert not mock_docling_extract.called
    assert [page.page_number for page in result.pages] == [2, 3]
