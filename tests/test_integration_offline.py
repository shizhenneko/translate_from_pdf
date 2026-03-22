from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from pdf_translate.config import Settings
from pdf_translate.marker_adapter import MarkerResult
from pdf_translate.pipeline import run_pipeline
from pdf_translate.translator import FakeTranslator


@respx.mock
def test_offline_full_pipeline_with_mocked_http(monkeypatch, tmp_path, sample_pdf_path):
    url = "https://example.com/n14.pdf"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=sample_pdf_path.read_bytes(),
        )
    )

    settings = Settings(
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
        ocr_text_threshold=1,
        ocr_lang="eng",
        max_concurrency=1,
        retry_max_attempts=2,
        cache_dir=tmp_path / ".cache",
        cjk_font_path=None,
    )

    def fake_marker(pdf_path, output_dir, command="marker_single", force_ocr=False):
        rendered_dir = output_dir / "marker"
        rendered_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = rendered_dir / "source.md"
        markdown_path.write_text("# Intro\n\nHello world.\n", encoding="utf-8")
        return MarkerResult(markdown_path=markdown_path, image_paths=[])

    monkeypatch.setattr("pdf_translate.pipeline.run_marker", fake_marker)

    output = tmp_path / "n14.zh.md"
    result = run_pipeline(
        url=url,
        settings=settings,
        output_path=output,
        translator=FakeTranslator(lambda t: "中译:" + t),
    )

    assert result.output_markdown.exists()
    text = result.output_markdown.read_text(encoding="utf-8")

    assert "中译" in text
