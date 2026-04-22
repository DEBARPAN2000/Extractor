"""Extraction backends."""

from text_extractor.backends import docling_backend
from text_extractor.backends import pdf2image_backend
from text_extractor.backends import pdfplumber_backend
from text_extractor.backends import pymupdf_backend
from text_extractor.backends import pypdf_backend
from text_extractor.backends import tesseract_backend

__all__ = [
    "docling_backend",
    "pdf2image_backend",
    "pdfplumber_backend",
    "pymupdf_backend",
    "pypdf_backend",
    "tesseract_backend",
]
