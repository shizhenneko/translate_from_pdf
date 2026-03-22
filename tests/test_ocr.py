from __future__ import annotations

import pytest

from pdf_translate.errors import OCRError
from pdf_translate.extractor import extract_pdf
from pdf_translate.ocr import apply_ocr_fallback


def test_ocr_fallback_triggers_for_low_text_page(scanned_like_pdf_path):
    pages = extract_pdf(scanned_like_pdf_path)
    calls = {"n": 0}

    def fake_ocr(_page, _lang):
        calls["n"] += 1
        return "recognized content from ocr"

    result = apply_ocr_fallback(
        scanned_like_pdf_path,
        pages,
        threshold=50,
        lang="eng",
        ocr_func=fake_ocr,
    )

    assert calls["n"] == 1
    assert result[0].used_ocr is True
    assert "recognized" in result[0].text


def test_ocr_fallback_not_triggered_for_normal_text(sample_pdf_path):
    pages = extract_pdf(sample_pdf_path)
    calls = {"n": 0}

    def fake_ocr(_page, _lang):
        calls["n"] += 1
        return "should not be called"

    result = apply_ocr_fallback(
        sample_pdf_path,
        pages,
        threshold=10,
        lang="eng",
        ocr_func=fake_ocr,
    )

    assert calls["n"] == 0
    assert all(page.used_ocr is False for page in result)


def test_ocr_errors_are_wrapped(scanned_like_pdf_path):
    pages = extract_pdf(scanned_like_pdf_path)

    def bad_ocr(_page, _lang):
        raise RuntimeError("bad")

    with pytest.raises(OCRError):
        apply_ocr_fallback(
            scanned_like_pdf_path,
            pages,
            threshold=50,
            lang="eng",
            ocr_func=bad_ocr,
        )
