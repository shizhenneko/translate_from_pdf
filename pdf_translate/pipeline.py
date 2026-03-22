"""Pipeline orchestration."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import re
import shutil
import uuid
from typing import Dict, Optional

import fitz

from .config import Settings
from .downloader import download_pdf
from .errors import ConfigError, PDFTranslateError
from .marker_adapter import run_marker
from .markdown_translate import translate_markdown
from .text_normalize import count_control_chars
from .translator import BaseTranslator, LLMTranslator, TranslationCache
from .types import PipelineResult

logger = logging.getLogger(__name__)

_IMAGE_LINK_RE = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")


def _default_output_path(base_name: str) -> Path:
    return Path(base_name + ".zh.md")


def _new_job_id() -> str:
    return datetime.utcnow().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]


def _public_output_dir() -> Path:
    return Path.cwd() / "pdfs"


def _artifact_stem(input_pdf: Path) -> str:
    return input_pdf.stem


def _manifest_path(job_dir: Path) -> Path:
    return job_dir / "manifest.json"


def _read_manifest(job_dir: Path) -> Dict[str, object]:
    path = _manifest_path(job_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(job_dir: Path, payload: Dict[str, object]) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    path = _manifest_path(job_dir)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _update_manifest(job_dir: Path, **updates: object) -> Dict[str, object]:
    payload = _read_manifest(job_dir)
    payload.update(updates)
    _write_manifest(job_dir, payload)
    return payload


def _copy_input_pdf(input_pdf: Path, job_dir: Path) -> Path:
    source_dir = job_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    destination = source_dir / input_pdf.name
    if input_pdf.resolve() != destination.resolve():
        shutil.copy2(input_pdf, destination)
    return destination


def _build_translator(settings: Settings) -> LLMTranslator:
    if not settings.llm_api_key or not settings.llm_base_url or not settings.llm_model:
        raise ConfigError(
            "LLM_API_KEY, LLM_BASE_URL, LLM_MODEL are required for online translation"
        )
    cache = TranslationCache(settings.cache_dir)
    return LLMTranslator(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        max_attempts=settings.retry_max_attempts,
        cache=cache,
    )


def _count_spans(doc) -> tuple:
    translatable = 0
    passthrough = 0
    for section in doc.sections:
        for paragraph in section.paragraphs:
            for span in paragraph.spans:
                if span.translatable:
                    translatable += 1
                else:
                    passthrough += 1
    return translatable, passthrough


def _count_doc_control_chars(doc) -> int:
    count = 0
    count += count_control_chars(doc.title)
    for section in doc.sections:
        count += count_control_chars(section.heading)
        for paragraph in section.paragraphs:
            for span in paragraph.spans:
                count += count_control_chars(span.text)
    return count


def _count_pdf_pages(pdf_path: Path) -> int:
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def _count_markdown_sections(markdown_text: str) -> int:
    count = 0
    for line in markdown_text.splitlines():
        if line.lstrip().startswith("#"):
            count += 1
    return count


def _localize_markdown_assets(
    markdown_text: str,
    *,
    markdown_path: Path,
    assets_dir: Path,
) -> str:
    assets_dir.mkdir(parents=True, exist_ok=True)
    copied: Dict[Path, str] = {}
    used_names = set()

    def repl(match: re.Match) -> str:
        prefix, raw_target, suffix = match.groups()
        target = raw_target.strip()
        if "://" in target:
            return match.group(0)

        source = (markdown_path.parent / target).resolve()
        if not source.exists() or not source.is_file():
            return match.group(0)

        if source not in copied:
            stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem) or "asset"
            candidate = stem + source.suffix.lower()
            index = 1
            while candidate in used_names:
                candidate = "%s-%d%s" % (stem, index, source.suffix.lower())
                index += 1
            used_names.add(candidate)
            destination = assets_dir / candidate
            shutil.copy2(source, destination)
            copied[source] = "assets/" + candidate
        return prefix + copied[source] + suffix

    localized = _IMAGE_LINK_RE.sub(repl, markdown_text)
    return localized


def run_markdown_translation(
    markdown_path: Path,
    settings: Settings,
    output_path: Optional[Path] = None,
    translator: Optional[BaseTranslator] = None,
) -> Path:
    translator = translator or _build_translator(settings)
    source_text = markdown_path.read_text(encoding="utf-8")
    translated = translate_markdown(
        source_text,
        translator=translator,
        max_chunk_chars=settings.markdown_chunk_chars,
        symbol_fix_mode=settings.symbol_fix_mode,
    )
    final_output = output_path or markdown_path.with_name(markdown_path.stem + ".zh.md")
    final_output.parent.mkdir(parents=True, exist_ok=True)
    final_output.write_text(translated, encoding="utf-8")
    return final_output


def run_file_pipeline(
    input_pdf: Path,
    *,
    settings: Settings,
    job_dir: Optional[Path] = None,
    translator: Optional[BaseTranslator] = None,
    output_markdown_path: Optional[Path] = None,
    source_reference: Optional[str] = None,
) -> PipelineResult:
    job_dir = job_dir or (settings.jobs_dir / _new_job_id())
    intermediate_dir = job_dir / "intermediate"
    pdfs_dir = _public_output_dir()
    assets_dir = pdfs_dir / "assets"
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    working_pdf = _copy_input_pdf(input_pdf, job_dir)
    initial_payload = {
        "job_id": job_dir.name,
        "status": "running",
        "stage": "input",
        "error": None,
        "input_pdf": str(working_pdf),
        "marker_markdown": None,
        "translated_markdown": None,
        "output_markdown": None,
    }
    _write_manifest(job_dir, initial_payload)

    stable_marker_md: Optional[Path] = None
    translated_md_path: Optional[Path] = None
    artifact_stem = _artifact_stem(working_pdf)
    default_output_markdown = pdfs_dir / (artifact_stem + ".md")
    stage = "marker"

    try:
        _update_manifest(job_dir, stage=stage)
        logger.info(
            "marker.start input=%s command=%s first_run_may_download_models=true",
            working_pdf,
            settings.marker_command,
        )
        marker_result = run_marker(
            working_pdf,
            output_dir=intermediate_dir,
            command=settings.marker_command,
            force_ocr=settings.marker_force_ocr,
        )

        stable_marker_md = intermediate_dir / "source.md"
        if marker_result.markdown_path.resolve() != stable_marker_md.resolve():
            shutil.copy2(marker_result.markdown_path, stable_marker_md)
        else:
            stable_marker_md = marker_result.markdown_path

        localized_markdown = _localize_markdown_assets(
            stable_marker_md.read_text(encoding="utf-8"),
            markdown_path=stable_marker_md,
            assets_dir=assets_dir,
        )

        stage = "translate"
        _update_manifest(job_dir, stage=stage, marker_markdown=str(stable_marker_md))
        active_translator = translator or _build_translator(settings)
        translated_markdown = translate_markdown(
            localized_markdown,
            translator=active_translator,
            max_chunk_chars=settings.markdown_chunk_chars,
            symbol_fix_mode=settings.symbol_fix_mode,
        )
        translated_md_path = default_output_markdown
        translated_md_path.write_text(translated_markdown, encoding="utf-8")

        final_output_markdown = translated_md_path
        if (
            output_markdown_path is not None
            and output_markdown_path.resolve() != translated_md_path.resolve()
        ):
            output_markdown_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(translated_md_path, output_markdown_path)
            final_output_markdown = output_markdown_path

        result = PipelineResult(
            downloaded_pdf=working_pdf,
            output_markdown=final_output_markdown,
            page_count=_count_pdf_pages(working_pdf),
            section_count=_count_markdown_sections(translated_markdown),
            job_id=job_dir.name,
            input_pdf=input_pdf,
            marker_markdown=stable_marker_md,
            translated_markdown=translated_md_path,
            status="succeeded",
            stage="done",
        )
        _update_manifest(
            job_dir,
            status="succeeded",
            stage="done",
            error=None,
            output_markdown=str(final_output_markdown),
        )
        return result
    except PDFTranslateError as exc:
        _update_manifest(
            job_dir,
            status="failed",
            stage=stage,
            error=str(exc),
            marker_markdown=str(stable_marker_md) if stable_marker_md else None,
            translated_markdown=str(translated_md_path) if translated_md_path else None,
        )
        raise
    except Exception as exc:
        _update_manifest(
            job_dir,
            status="failed",
            stage=stage,
            error=str(exc),
            marker_markdown=str(stable_marker_md) if stable_marker_md else None,
            translated_markdown=str(translated_md_path) if translated_md_path else None,
        )
        raise


def run_pipeline(
    url: str,
    settings: Settings,
    output_path: Optional[Path] = None,
    max_pages: Optional[int] = None,
    translator: Optional[BaseTranslator] = None,
    job_dir: Optional[Path] = None,
) -> PipelineResult:
    logger.info("download.start url=%s", url)
    download_result = download_pdf(url=url, output_dir=settings.cache_dir / "downloads")
    result = run_file_pipeline(
        download_result.output_path,
        settings=settings,
        job_dir=job_dir,
        translator=translator,
        output_markdown_path=output_path,
        source_reference=url,
    )
    result.downloaded_pdf = download_result.output_path
    return result
