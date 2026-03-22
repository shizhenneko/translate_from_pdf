from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf_translate.config import Settings
from pdf_translate.errors import MarkerError
from pdf_translate.marker_adapter import MarkerResult
from pdf_translate.pipeline import run_file_pipeline
from pdf_translate.translator import FakeTranslator


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
        ocr_text_threshold=1,
        ocr_lang="eng",
        max_concurrency=1,
        retry_max_attempts=2,
        cache_dir=tmp_path / ".cache",
        cjk_font_path=None,
        jobs_dir=tmp_path / "jobs",
        marker_command="marker_single",
        marker_output_format="markdown",
        marker_force_ocr=False,
        web_host="127.0.0.1",
        web_port=10001,
        max_upload_mb=30,
        markdown_chunk_chars=4000,
    )


def test_run_file_pipeline_creates_manifest_and_outputs(
    monkeypatch, tmp_path, sample_pdf_path
):
    settings = _settings(tmp_path)
    job_dir = tmp_path / "job-001"

    def fake_marker(pdf_path, output_dir, command="marker_single", force_ocr=False):
        rendered_dir = output_dir / "marker"
        rendered_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = rendered_dir / "source.md"
        markdown_path.write_text("# Intro\n\nHello world.\n", encoding="utf-8")
        return MarkerResult(markdown_path=markdown_path, image_paths=[])

    monkeypatch.setattr("pdf_translate.pipeline.run_marker", fake_marker)
    monkeypatch.chdir(tmp_path)

    result = run_file_pipeline(
        sample_pdf_path,
        settings=settings,
        job_dir=job_dir,
        translator=FakeTranslator(lambda text: text.replace("Hello world.", "你好世界。")),
    )

    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))

    assert result.input_pdf == sample_pdf_path
    assert result.marker_markdown.exists()
    assert result.translated_markdown.exists()
    assert result.output_markdown.exists()
    assert result.translated_markdown == tmp_path / "pdfs" / "sample.md"
    assert result.output_markdown == tmp_path / "pdfs" / "sample.md"
    assert (tmp_path / "pdfs" / "assets").exists()
    assert not (job_dir / "pdfs").exists()
    assert not (job_dir / "output").exists()
    assert manifest["status"] == "succeeded"
    assert manifest["stage"] == "done"


def test_run_file_pipeline_records_failure_manifest(
    monkeypatch, tmp_path, sample_pdf_path
):
    settings = _settings(tmp_path)
    job_dir = tmp_path / "job-002"

    def bad_marker(pdf_path, output_dir, command="marker_single", force_ocr=False):
        raise MarkerError("marker blew up")

    monkeypatch.setattr("pdf_translate.pipeline.run_marker", bad_marker)

    with pytest.raises(MarkerError):
        run_file_pipeline(sample_pdf_path, settings=settings, job_dir=job_dir)

    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["stage"] == "marker"
    assert "marker blew up" in manifest["error"]
