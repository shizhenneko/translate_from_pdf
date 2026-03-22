from __future__ import annotations

import os

import pytest

from pdf_translate.config import load_settings
from pdf_translate.pipeline import run_pipeline


@pytest.mark.e2e_live
def test_live_real_url_translation(tmp_path):
    if os.getenv("PDF_TRANSLATE_RUN_LIVE_TESTS") != "1":
        pytest.skip("set PDF_TRANSLATE_RUN_LIVE_TESTS=1 to run live network tests")

    if not os.path.exists(".env"):
        pytest.skip(".env not found")

    settings = load_settings(require_online=True)

    out = tmp_path / "n14.zh.md"
    result = run_pipeline(
        url="https://www.eecs70.org/assets/pdf/notes/n14.pdf",
        settings=settings,
        output_path=out,
        max_pages=4,
    )

    assert result.output_markdown.exists()
    text = result.output_markdown.read_text(encoding="utf-8")

    assert len(text.strip()) > 0
