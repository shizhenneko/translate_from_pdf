from __future__ import annotations

import io
import time
from pathlib import Path

from pdf_translate.config import Settings
from pdf_translate.pipeline import PipelineResult
from pdf_translate.web import create_app


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


def test_web_job_upload_poll_and_download(tmp_path, sample_pdf_path):
    settings = _settings(tmp_path)

    def fake_runner(input_pdf, settings, job_dir, translator=None):
        intermediate = job_dir / "intermediate"
        output = job_dir / "output"
        intermediate.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        marker_markdown = intermediate / "source.md"
        translated_markdown = output / "result.zh.md"
        marker_markdown.write_text("# Intro\n\nHello world.\n", encoding="utf-8")
        translated_markdown.write_text("# 介绍\n\n你好世界。\n", encoding="utf-8")
        return PipelineResult(
            downloaded_pdf=input_pdf,
            output_markdown=translated_markdown,
            page_count=1,
            section_count=1,
            job_id=job_dir.name,
            input_pdf=input_pdf,
            marker_markdown=marker_markdown,
            translated_markdown=translated_markdown,
            status="succeeded",
            stage="done",
        )

    app = create_app(settings=settings, pipeline_runner=fake_runner)
    client = app.test_client()

    response = client.post(
        "/api/jobs/pdf",
        data={"file": (io.BytesIO(sample_pdf_path.read_bytes()), "sample.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["status"] in {"queued", "running", "succeeded"}
    job_id = payload["job_id"]

    final_status = None
    for _ in range(40):
        status_response = client.get(f"/api/jobs/{job_id}")
        assert status_response.status_code == 200
        final_status = status_response.get_json()
        if final_status["status"] == "succeeded":
            break
        time.sleep(0.05)

    assert final_status is not None
    assert final_status["status"] == "succeeded"
    assert final_status["translated_markdown"].endswith("result.zh.md")

    download_md = client.get(f"/api/jobs/{job_id}/download/md")
    assert download_md.status_code == 200
    assert "attachment" in download_md.headers["Content-Disposition"]

def test_web_job_url_submit_poll_and_download(tmp_path, sample_pdf_path):
    settings = _settings(tmp_path)

    def fake_url_runner(url, settings, job_dir, translator=None):
        source = job_dir / "source"
        intermediate = job_dir / "intermediate"
        output = job_dir / "output"
        source.mkdir(parents=True, exist_ok=True)
        intermediate.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)

        input_pdf = source / "remote.pdf"
        marker_markdown = intermediate / "source.md"
        translated_markdown = output / "result.zh.md"

        input_pdf.write_bytes(sample_pdf_path.read_bytes())
        marker_markdown.write_text("# Intro\n\nRemote source.\n", encoding="utf-8")
        translated_markdown.write_text("# 介绍\n\n远程文档。\n", encoding="utf-8")

        return PipelineResult(
            downloaded_pdf=input_pdf,
            output_markdown=translated_markdown,
            page_count=1,
            section_count=1,
            job_id=job_dir.name,
            input_pdf=input_pdf,
            marker_markdown=marker_markdown,
            translated_markdown=translated_markdown,
            status="succeeded",
            stage="done",
        )

    app = create_app(
        settings=settings,
        url_pipeline_runner=fake_url_runner,
    )
    client = app.test_client()

    response = client.post(
        "/api/jobs/url",
        json={"url": "https://example.com/sample.pdf"},
    )
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["status"] in {"queued", "running", "succeeded"}
    assert payload["source_url"] == "https://example.com/sample.pdf"
    job_id = payload["job_id"]

    final_status = None
    for _ in range(40):
        status_response = client.get(f"/api/jobs/{job_id}")
        assert status_response.status_code == 200
        final_status = status_response.get_json()
        if final_status["status"] == "succeeded":
            break
        time.sleep(0.05)

    assert final_status is not None
    assert final_status["status"] == "succeeded"
    assert final_status["source_url"] == "https://example.com/sample.pdf"

    download_md = client.get(f"/api/jobs/{job_id}/download/md")
    assert download_md.status_code == 200

def test_web_job_url_requires_pdf_link(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings=settings)
    client = app.test_client()

    response = client.post(
        "/api/jobs/url",
        json={"url": "https://example.com/index.html"},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert "pdf" in payload["error"].lower()
