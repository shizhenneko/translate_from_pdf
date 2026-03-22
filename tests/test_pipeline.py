from __future__ import annotations

from pathlib import Path

import pytest

from pdf_translate.config import Settings
from pdf_translate.downloader import DownloadResult
from pdf_translate.errors import ConfigError
from pdf_translate.pipeline import run_pipeline
from pdf_translate.translator import FakeTranslator
from pdf_translate.types import PipelineResult


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
        ocr_text_threshold=1,
        ocr_lang="eng",
        max_concurrency=2,
        retry_max_attempts=2,
        cache_dir=tmp_path / ".cache",
        cjk_font_path=None,
    )


def test_pipeline_offline_with_fake_translator(monkeypatch, tmp_path, sample_pdf_path):
    settings = _settings(tmp_path)

    def fake_download(url, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        copied = output_dir / "sample.pdf"
        copied.write_bytes(sample_pdf_path.read_bytes())
        return DownloadResult(source_url=url, output_path=copied, base_name="sample")

    monkeypatch.setattr("pdf_translate.pipeline.download_pdf", fake_download)
    captured = {}

    def fake_run_file_pipeline(
        input_pdf,
        *,
        settings,
        job_dir=None,
        translator=None,
        output_markdown_path=None,
        source_reference=None,
    ):
        captured["input_pdf"] = input_pdf
        captured["output_markdown_path"] = output_markdown_path
        captured["source_reference"] = source_reference
        final_output = output_markdown_path or (tmp_path / "pdfs" / "sample.md")
        final_output.parent.mkdir(parents=True, exist_ok=True)
        final_output.write_text("# 示例\n", encoding="utf-8")
        return PipelineResult(
            downloaded_pdf=input_pdf,
            output_markdown=final_output,
            page_count=2,
            section_count=2,
        )

    monkeypatch.setattr("pdf_translate.pipeline.run_file_pipeline", fake_run_file_pipeline)

    out = tmp_path / "result.zh.md"
    result = run_pipeline(
        url="https://example.com/sample.pdf",
        settings=settings,
        output_path=out,
        translator=FakeTranslator(),
    )

    assert result.output_markdown == out
    assert out.exists()
    assert captured["input_pdf"].name == "sample.pdf"
    assert captured["source_reference"] == "https://example.com/sample.pdf"


def test_pipeline_requires_online_settings_without_translator(monkeypatch, tmp_path, sample_pdf_path):
    settings = _settings(tmp_path)

    def fake_download(url, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        copied = output_dir / "sample.pdf"
        copied.write_bytes(sample_pdf_path.read_bytes())
        return DownloadResult(source_url=url, output_path=copied, base_name="sample")

    monkeypatch.setattr("pdf_translate.pipeline.download_pdf", fake_download)
    monkeypatch.setattr(
        "pdf_translate.pipeline.run_file_pipeline",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConfigError("missing online config")),
    )

    with pytest.raises(ConfigError):
        run_pipeline(url="https://example.com/sample.pdf", settings=settings)


def test_pipeline_default_output_name(monkeypatch, tmp_path, sample_pdf_path):
    settings = _settings(tmp_path)

    def fake_download(url, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        copied = output_dir / "n14.pdf"
        copied.write_bytes(sample_pdf_path.read_bytes())
        return DownloadResult(source_url=url, output_path=copied, base_name="n14")

    monkeypatch.setattr("pdf_translate.pipeline.download_pdf", fake_download)
    monkeypatch.chdir(tmp_path)

    def fake_run_file_pipeline(
        input_pdf,
        *,
        settings,
        job_dir=None,
        translator=None,
        output_markdown_path=None,
        source_reference=None,
    ):
        pdfs_dir = tmp_path / "pdfs"
        pdfs_dir.mkdir(parents=True, exist_ok=True)
        translated_md = pdfs_dir / "n14.md"
        translated_md.write_text("# 介绍\n", encoding="utf-8")
        return PipelineResult(
            downloaded_pdf=input_pdf,
            output_markdown=translated_md,
            page_count=2,
            section_count=2,
            translated_markdown=translated_md,
        )

    monkeypatch.setattr("pdf_translate.pipeline.run_file_pipeline", fake_run_file_pipeline)

    result = run_pipeline(
        url="https://example.com/n14.pdf",
        settings=settings,
        translator=FakeTranslator(),
    )

    assert result.output_markdown == tmp_path / "pdfs" / "n14.md"
    assert (tmp_path / "pdfs" / "n14.md").exists()
