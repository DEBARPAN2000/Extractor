"""Tests for the smart router."""

from pathlib import Path
from unittest.mock import patch

from text_extractor.router import detect_strategy, extract


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
