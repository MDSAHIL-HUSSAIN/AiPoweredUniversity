from dataclasses import dataclass
from pathlib import Path
import os
import shutil

import pymupdf  # PyMuPDF
from PIL import Image
import pytesseract


@dataclass
class PageText:
    page: int
    text: str


MIN_TEXT_LENGTH = 50


def _ocr_page(page: pymupdf.Page) -> str:
    """Extract text from a PDF page using OCR."""
    configured = os.getenv("TESSERACT_CMD")
    executable = configured or shutil.which("tesseract")
    if not executable:
        raise RuntimeError(
            "This PDF page needs OCR, but Tesseract is not installed. "
            "Install Tesseract and optionally set TESSERACT_CMD to its executable."
        )
    pytesseract.pytesseract.tesseract_cmd = executable
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)

    image = Image.frombytes(
        "RGB",
        [pixmap.width, pixmap.height],
        pixmap.samples,
    )

    return pytesseract.image_to_string(image).strip()


def parse_pdf(file_path: str | Path) -> list[PageText]:
    """
    Extract text from a PDF page-by-page.

    Uses normal PDF text extraction first.
    Falls back to OCR for pages with insufficient text.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    if file_path.suffix.lower() != ".pdf":
        raise ValueError("Input file must be a PDF.")

    pages: list[PageText] = []
    ocr_unavailable = False

    with pymupdf.open(file_path) as document:
        for page_number, page in enumerate(document, start=1):

            text = page.get_text("text").strip()

            # OCR fallback for scanned/image-heavy pages
            if len(text) < MIN_TEXT_LENGTH:
                try:
                    ocr_text = _ocr_page(page)
                    text = ocr_text or text
                except RuntimeError:
                    # Keep any embedded text and skip truly image-only/blank pages.
                    # If every page needs OCR, report the missing dependency below.
                    ocr_unavailable = True

            if text:
                pages.append(
                    PageText(
                        page=page_number,
                        text=text,
                    )
                )

    if not pages:
        if ocr_unavailable:
            raise RuntimeError(
                "This PDF needs OCR, but Tesseract is not installed. Install "
                "Tesseract and optionally set TESSERACT_CMD to its executable."
            )
        raise ValueError(
            f"No text could be extracted from PDF: {file_path}"
        )

    return pages
