"""Environment-backed runtime settings."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
import platform
from typing import Dict, List, Optional, Sequence

from dotenv import load_dotenv

from .errors import ConfigError
from .text_normalize import allowed_symbol_fix_modes


@dataclass
class Settings:
    llm_api_key: Optional[str]
    llm_base_url: Optional[str]
    llm_model: Optional[str]
    ocr_text_threshold: int
    ocr_lang: str
    max_concurrency: int
    retry_max_attempts: int
    cache_dir: Path
    cjk_font_path: Optional[Path]
    math_font_path: Optional[Path] = None
    symbol_fix_mode: str = "conservative"
    jobs_dir: Path = Path(".jobs/pdf_translate")
    marker_command: str = "marker_single"
    marker_output_format: str = "markdown"
    marker_force_ocr: bool = False
    web_host: str = "127.0.0.1"
    web_port: int = 10001
    max_upload_mb: int = 30
    markdown_chunk_chars: int = 4000


_CRITICAL_ENV_KEYS: Sequence[str] = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "PDF_TRANSLATE_CJK_FONT_PATH",
    "PDF_TRANSLATE_MATH_FONT_PATH",
    "PDF_TRANSLATE_MARKER_COMMAND",
)

_WINDOWS_CJK_FONT_CANDIDATES: Sequence[str] = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\arialuni.ttf",
)

_WINDOWS_MATH_FONT_CANDIDATES: Sequence[str] = (
    r"C:\Windows\Fonts\seguisym.ttf",
    r"C:\Windows\Fonts\cambria.ttc",
    r"C:\Windows\Fonts\arial.ttf",
)


def _read_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError("%s must be an integer, got %r" % (name, raw)) from exc
    if value < minimum:
        raise ConfigError("%s must be >= %d" % (name, minimum))
    return value


def _read_str(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if not value:
        return default
    return value


def _read_bool(name: str, default: bool = False) -> bool:
    value = _read_str(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError("%s must be a boolean-like value, got %r" % (name, value))


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _is_linux_style_path(value: str) -> bool:
    normalized = value.replace("\\", "/").strip().lower()
    return normalized.startswith("/usr/") or normalized.startswith("/mnt/")


def _first_existing_path(candidates: Sequence[str]) -> Optional[Path]:
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def _resolve_font_path(raw_value: Optional[str], *, candidates: Sequence[str]) -> Optional[Path]:
    if raw_value:
        explicit_path = Path(raw_value).expanduser()
        if explicit_path.exists():
            return explicit_path
        if not _is_windows() or not _is_linux_style_path(raw_value):
            return explicit_path

    if _is_windows():
        return _first_existing_path(candidates)
    return Path(raw_value).expanduser() if raw_value else None


def _strip_export_prefix(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith("export "):
        return stripped[len("export ") :].lstrip()
    return stripped


def _find_duplicate_env_keys(env_file: str, keys: Sequence[str]) -> Dict[str, List[int]]:
    path = Path(env_file)
    if not path.exists():
        return {}

    seen_line: Dict[str, int] = {}
    duplicates: Dict[str, List[int]] = {}

    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            line = _strip_export_prefix(raw.strip())
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key not in keys:
                continue
            if key in seen_line:
                duplicates.setdefault(key, [seen_line[key]]).append(line_no)
            else:
                seen_line[key] = line_no
    return duplicates


def _format_duplicate_env_message(env_file: str, duplicates: Dict[str, List[int]]) -> str:
    parts = []
    for key in sorted(duplicates):
        lines = ",".join(str(num) for num in duplicates[key])
        parts.append("%s (lines %s)" % (key, lines))
    return (
        "Duplicate keys found in %s: %s. Keep only one value per key."
        % (env_file, "; ".join(parts))
    )


def load_settings(env_file: str = ".env", require_online: bool = False) -> Settings:
    """Load settings from .env and process env vars.

    Parameters
    ----------
    env_file:
        Dotenv path to load if present.
    require_online:
        When true, enforce LLM_* variables needed for real translation.
    """

    duplicates = _find_duplicate_env_keys(env_file, _CRITICAL_ENV_KEYS)
    if duplicates:
        raise ConfigError(_format_duplicate_env_message(env_file, duplicates))

    load_dotenv(dotenv_path=env_file, override=False)

    llm_api_key = _read_str("LLM_API_KEY")
    llm_base_url = _read_str("LLM_BASE_URL")
    llm_model = _read_str("LLM_MODEL")

    if require_online:
        missing = []
        if not llm_api_key:
            missing.append("LLM_API_KEY")
        if not llm_base_url:
            missing.append("LLM_BASE_URL")
        if not llm_model:
            missing.append("LLM_MODEL")
        if missing:
            raise ConfigError(
                "Missing required online settings in .env: %s" % ", ".join(missing)
            )

    ocr_text_threshold = _read_int("PDF_TRANSLATE_OCR_TEXT_THRESHOLD", default=50, minimum=0)
    ocr_lang = _read_str("PDF_TRANSLATE_OCR_LANG", default="eng") or "eng"
    max_concurrency = _read_int("PDF_TRANSLATE_MAX_CONCURRENCY", default=2, minimum=1)
    retry_max_attempts = _read_int("PDF_TRANSLATE_RETRY_MAX_ATTEMPTS", default=3, minimum=1)
    cache_dir = Path(_read_str("PDF_TRANSLATE_CACHE_DIR", default=".cache/pdf_translate") or ".cache/pdf_translate")

    cjk_font_raw = _read_str("PDF_TRANSLATE_CJK_FONT_PATH")
    cjk_font_path = _resolve_font_path(
        cjk_font_raw,
        candidates=_WINDOWS_CJK_FONT_CANDIDATES,
    )
    math_font_raw = _read_str("PDF_TRANSLATE_MATH_FONT_PATH")
    math_font_path = _resolve_font_path(
        math_font_raw,
        candidates=_WINDOWS_MATH_FONT_CANDIDATES,
    )

    symbol_fix_mode = (_read_str("PDF_TRANSLATE_SYMBOL_FIX_MODE", default="conservative") or "conservative").lower()
    allowed_modes = set(allowed_symbol_fix_modes())
    if symbol_fix_mode not in allowed_modes:
        raise ConfigError(
            "PDF_TRANSLATE_SYMBOL_FIX_MODE must be one of: %s"
            % ", ".join(sorted(allowed_modes))
        )

    jobs_dir = Path(
        _read_str("PDF_TRANSLATE_JOBS_DIR", default=".jobs/pdf_translate")
        or ".jobs/pdf_translate"
    )
    marker_command = (
        _read_str("PDF_TRANSLATE_MARKER_COMMAND", default="marker_single")
        or "marker_single"
    )
    marker_output_format = (
        _read_str("PDF_TRANSLATE_MARKER_OUTPUT_FORMAT", default="markdown")
        or "markdown"
    ).lower()
    if marker_output_format != "markdown":
        raise ConfigError("PDF_TRANSLATE_MARKER_OUTPUT_FORMAT must currently be markdown")
    marker_force_ocr = _read_bool("PDF_TRANSLATE_MARKER_FORCE_OCR", default=False)
    web_host = _read_str("PDF_TRANSLATE_WEB_HOST", default="127.0.0.1") or "127.0.0.1"
    web_port = _read_int("PDF_TRANSLATE_WEB_PORT", default=10001, minimum=1)
    max_upload_mb = _read_int("PDF_TRANSLATE_MAX_UPLOAD_MB", default=30, minimum=1)
    markdown_chunk_chars = _read_int("PDF_TRANSLATE_MARKDOWN_CHUNK_CHARS", default=4000, minimum=200)

    return Settings(
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        ocr_text_threshold=ocr_text_threshold,
        ocr_lang=ocr_lang,
        max_concurrency=max_concurrency,
        retry_max_attempts=retry_max_attempts,
        cache_dir=cache_dir,
        cjk_font_path=cjk_font_path,
        math_font_path=math_font_path,
        symbol_fix_mode=symbol_fix_mode,
        jobs_dir=jobs_dir,
        marker_command=marker_command,
        marker_output_format=marker_output_format,
        marker_force_ocr=marker_force_ocr,
        web_host=web_host,
        web_port=web_port,
        max_upload_mb=max_upload_mb,
        markdown_chunk_chars=markdown_chunk_chars,
    )


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
