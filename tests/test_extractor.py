from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_translate.errors import ExtractError
from pdf_translate.extractor import extract_pdf, infer_title


def test_extract_pdf_page_count_matches_document(sample_pdf_path):
    pages = extract_pdf(sample_pdf_path)

    with fitz.open(sample_pdf_path) as doc:
        assert len(pages) == doc.page_count


def test_extract_pdf_collects_text(sample_pdf_path):
    pages = extract_pdf(sample_pdf_path)
    joined = "\n".join(page.text for page in pages)

    assert "Introduction" in joined
    assert any(page.text_len > 0 for page in pages)


def test_extract_pdf_collects_images(sample_pdf_path):
    pages = extract_pdf(sample_pdf_path)
    image_count = sum(len(page.images) for page in pages)

    assert image_count >= 1


def test_extract_pdf_missing_file_raises(tmp_path):
    missing = tmp_path / "missing.pdf"
    with pytest.raises(ExtractError):
        extract_pdf(missing)


def test_infer_title_uses_first_non_empty_line(sample_pdf_path):
    pages = extract_pdf(sample_pdf_path)
    title = infer_title(pages, fallback="fallback")
    assert title
    assert title != "fallback"
