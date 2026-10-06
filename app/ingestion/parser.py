from dataclasses import dataclass
from pathlib import Path
import os

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

    # Optional Windows Tesseract configuration
    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    pages: list[PageText] = []

    with pymupdf.open(file_path) as document:
        for page_number, page in enumerate(document, start=1):

            text = page.get_text("text").strip()

            # OCR fallback for scanned/image-heavy pages
            if len(text) < MIN_TEXT_LENGTH:
                text = _ocr_page(page)

            if text:
                pages.append(
                    PageText(
                        page=page_number,
                        text=text,
                    )
                )

    if not pages:
        raise ValueError(
            f"No text could be extracted from PDF: {file_path}"
        )

    return pages