from __future__ import annotations

from pathlib import Path

import pytest

import pdf_translate.config as config_module
from pdf_translate.config import load_settings
from pdf_translate.errors import ConfigError


def test_load_settings_defaults(monkeypatch):
    monkeypatch.delenv("PDF_TRANSLATE_OCR_TEXT_THRESHOLD", raising=False)
    monkeypatch.delenv("PDF_TRANSLATE_MAX_CONCURRENCY", raising=False)

    settings = load_settings(env_file=".env.not.exists", require_online=False)

    assert settings.ocr_text_threshold == 50
    assert settings.max_concurrency == 2
    assert settings.retry_max_attempts == 3
    assert settings.cache_dir.as_posix().endswith(".cache/pdf_translate")
    if config_module.platform.system().lower() == "windows":
        assert settings.math_font_path is not None
    else:
        assert settings.math_font_path is None
    assert settings.symbol_fix_mode == "conservative"
    assert settings.jobs_dir.as_posix().endswith(".jobs/pdf_translate")
    assert settings.marker_command == "marker_single"
    assert settings.web_port == 10001
    assert settings.markdown_chunk_chars == 4000


def test_load_settings_require_online_missing(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(ConfigError):
        load_settings(env_file=".env.not.exists", require_online=True)


def test_load_settings_int_validation(monkeypatch):
    monkeypatch.setenv("PDF_TRANSLATE_MAX_CONCURRENCY", "abc")

    with pytest.raises(ConfigError):
        load_settings(env_file=".env.not.exists", require_online=False)


def test_load_settings_reads_env_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "LLM_API_KEY=k",
                "LLM_BASE_URL=https://x",
                "LLM_MODEL=m",
                "PDF_TRANSLATE_CJK_FONT_PATH=/tmp/font.ttc",
                "PDF_TRANSLATE_MATH_FONT_PATH=/tmp/math.ttf",
                "PDF_TRANSLATE_OCR_TEXT_THRESHOLD=12",
                "PDF_TRANSLATE_SYMBOL_FIX_MODE=off",
                "PDF_TRANSLATE_JOBS_DIR=/tmp/jobs",
                "PDF_TRANSLATE_MARKER_COMMAND=marker_single",
                "PDF_TRANSLATE_MARKER_FORCE_OCR=true",
                "PDF_TRANSLATE_WEB_PORT=11001",
                "PDF_TRANSLATE_MARKDOWN_CHUNK_CHARS=5000",
            ]
        ),
        encoding="utf-8",
    )

    for key in [
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "PDF_TRANSLATE_CJK_FONT_PATH",
        "PDF_TRANSLATE_MATH_FONT_PATH",
        "PDF_TRANSLATE_OCR_TEXT_THRESHOLD",
        "PDF_TRANSLATE_SYMBOL_FIX_MODE",
        "PDF_TRANSLATE_JOBS_DIR",
        "PDF_TRANSLATE_MARKER_COMMAND",
        "PDF_TRANSLATE_MARKER_FORCE_OCR",
        "PDF_TRANSLATE_WEB_PORT",
        "PDF_TRANSLATE_MARKDOWN_CHUNK_CHARS",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = load_settings(env_file=str(env_path), require_online=True)
    assert settings.llm_api_key == "k"
    assert settings.llm_base_url == "https://x"
    assert settings.llm_model == "m"
    assert settings.cjk_font_path == Path("/tmp/font.ttc")
    assert settings.math_font_path == Path("/tmp/math.ttf")
    assert settings.ocr_text_threshold == 12
    assert settings.symbol_fix_mode == "off"
    assert settings.jobs_dir == Path("/tmp/jobs")
    assert settings.marker_command == "marker_single"
    assert settings.marker_force_ocr is True
    assert settings.web_port == 11001
    assert settings.markdown_chunk_chars == 5000


def test_load_settings_fails_on_duplicate_critical_key(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "LLM_API_KEY=k",
                "LLM_BASE_URL=https://x",
                "LLM_MODEL=first",
                "LLM_MODEL=second",
            ]
        ),
        encoding="utf-8",
    )

    for key in ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ConfigError) as exc:
        load_settings(env_file=str(env_path), require_online=False)
    msg = str(exc.value)
    assert "LLM_MODEL" in msg
    assert "lines" in msg


def test_load_settings_rejects_invalid_symbol_fix_mode(monkeypatch):
    monkeypatch.setenv("PDF_TRANSLATE_SYMBOL_FIX_MODE", "aggressive")
    with pytest.raises(ConfigError):
        load_settings(env_file=".env.not.exists", require_online=False)


def test_load_settings_windows_falls_back_from_linux_font_path(monkeypatch):
    monkeypatch.setattr(config_module.platform, "system", lambda: "Windows")
    monkeypatch.setenv("PDF_TRANSLATE_CJK_FONT_PATH", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
    monkeypatch.setenv("PDF_TRANSLATE_MATH_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    monkeypatch.setattr(
        config_module.Path,
        "exists",
        lambda self: str(self) in {
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\seguisym.ttf",
        },
    )

    settings = load_settings(env_file=".env.not.exists", require_online=False)

    assert settings.cjk_font_path == Path(r"C:\Windows\Fonts\msyh.ttc")
    assert settings.math_font_path == Path(r"C:\Windows\Fonts\seguisym.ttf")
