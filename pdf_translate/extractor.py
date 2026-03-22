"""PDF text/image extraction."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import fitz

from .errors import ExtractError
from .types import ImageAsset, PageData


def _extract_images_for_page(doc: fitz.Document, page: fitz.Page, page_number: int) -> List[ImageAsset]:
    images = []
    for idx, image_info in enumerate(page.get_images(full=True)):
        xref = image_info[0]
        try:
            extracted = doc.extract_image(xref)
            image_bytes = extracted.get("image", b"")
            ext = extracted.get("ext", "bin")
            if image_bytes:
                images.append(
                    ImageAsset(
                        page_number=page_number,
                        image_id="p%d_img%d" % (page_number, idx),
                        ext=ext,
                        data=image_bytes,
                    )
                )
        except Exception:
            # best-effort image extraction; text extraction continues
            continue
    return images


def extract_pdf(pdf_path: Path, max_pages: Optional[int] = None) -> List[PageData]:
    if not pdf_path.exists():
        raise ExtractError("Input PDF does not exist: %s" % pdf_path)

    pages: List[PageData] = []
    try:
        with fitz.open(pdf_path) as doc:
            page_count = doc.page_count if max_pages is None else min(doc.page_count, max_pages)
            for idx in range(page_count):
                page = doc.load_page(idx)
                text = page.get_text("text") or ""
                images = _extract_images_for_page(doc, page, page_number=idx + 1)
                pages.append(
                    PageData(
                        page_number=idx + 1,
                        raw_text=text,
                        text=text,
                        text_len=len(text.strip()),
                        used_ocr=False,
                        images=images,
                    )
                )
    except Exception as exc:
        raise ExtractError("Failed to parse PDF %s: %s" % (pdf_path, exc)) from exc

    if not pages:
        raise ExtractError("PDF has no pages: %s" % pdf_path)
    return pages


def infer_title(pages: List[PageData], fallback: str = "Translated Document") -> str:
    for page in pages:
        for raw_line in page.text.splitlines():
            line = raw_line.strip()
            if line:
                return line[:120]
    return fallback
