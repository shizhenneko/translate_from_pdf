"""Domain errors with stable exit codes."""

from __future__ import annotations


class PDFTranslateError(Exception):
    """Base class for pipeline errors."""


class ConfigError(PDFTranslateError):
    """Invalid or missing configuration."""


class DownloadError(PDFTranslateError):
    """Failed to download or validate input PDF."""


class ExtractError(PDFTranslateError):
    """Failed while extracting PDF text or images."""


class OCRError(PDFTranslateError):
    """Failed while running OCR."""


class MarkerError(PDFTranslateError):
    """Failed while converting a document with Marker."""


class TranslateError(PDFTranslateError):
    """Failed while translating content."""


class RenderError(PDFTranslateError):
    """Failed while rendering output PDF."""


class JobError(PDFTranslateError):
    """Failed while handling an async job."""


EXIT_CODES = {
    ConfigError: 2,
    DownloadError: 3,
    ExtractError: 4,
    OCRError: 4,
    MarkerError: 4,
    TranslateError: 5,
    RenderError: 6,
    JobError: 7,
}


def exit_code_for(exc: Exception) -> int:
    for error_type, code in EXIT_CODES.items():
        if isinstance(exc, error_type):
            return code
    return 1
