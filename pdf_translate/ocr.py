"""OCR fallback for low-text pages."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Callable, List, Optional

import fitz

from .errors import OCRError
from .types import PageData


OCRFunc = Callable[[fitz.Page, str], str]


def ocr_page_text(page: fitz.Page, lang: str = "eng") -> str:
    try:
        import pytesseract
        from PIL import Image
    except Exception as exc:
        raise OCRError("OCR dependencies are missing: install pytesseract + pillow") from exc

    pix = page.get_pixmap(dpi=220, alpha=False)
    image = Image.open(BytesIO(pix.tobytes("png")))
    text = pytesseract.image_to_string(image, lang=lang)
    return text or ""


def apply_ocr_fallback(
    pdf_path: Path,
    pages: List[PageData],
    threshold: int = 50,
    lang: str = "eng",
    ocr_func: Optional[OCRFunc] = None,
) -> List[PageData]:
    """Run OCR only for pages with low extractable text length."""

    if ocr_func is None:
        ocr_func = ocr_page_text

    low_text_pages = [p for p in pages if p.text_len < threshold]
    if not low_text_pages:
        return pages

    try:
        with fitz.open(pdf_path) as doc:
            page_map = {page.page_number: page for page in pages}
            for page_data in low_text_pages:
                page = doc.load_page(page_data.page_number - 1)
                try:
                    ocr_text = ocr_func(page, lang)
                except Exception as exc:
                    raise OCRError(
                        "OCR failed for page %d: %s" % (page_data.page_number, exc)
                    ) from exc

                cleaned = (ocr_text or "").strip()
                if cleaned:
                    target = page_map[page_data.page_number]
                    target.text = cleaned
                    target.text_len = len(cleaned)
                    target.used_ocr = True
    except OCRError:
        raise
    except Exception as exc:
        raise OCRError("Failed OCR fallback processing: %s" % exc) from exc

    return pages
