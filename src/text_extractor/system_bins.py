"""Locate external binaries required by OCR backends."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def find_tesseract() -> str | None:
    """Find tesseract executable path."""
    direct = shutil.which("tesseract")
    if direct:
        return direct

    candidates = [
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def find_poppler_bin() -> str | None:
    """Find directory containing pdftoppm executable."""
    direct = shutil.which("pdftoppm")
    if direct:
        return str(Path(direct).parent)

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        base = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if base.exists():
            matches = list(base.rglob("pdftoppm.exe"))
            if matches:
                return str(matches[0].parent)

    candidates = [
        Path("C:/Program Files/poppler/Library/bin"),
        Path("C:/Program Files (x86)/poppler/Library/bin"),
    ]
    for c in candidates:
        if (c / "pdftoppm.exe").exists():
            return str(c)

    return None