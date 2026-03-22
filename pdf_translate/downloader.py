"""Download input PDF with validation and retries."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, unquote

import httpx

from .errors import DownloadError


_PDF_MAGIC = b"%PDF-"


@dataclass
class DownloadResult:
    source_url: str
    output_path: Path
    base_name: str


def sanitize_basename_from_url(url: str) -> str:
    parsed = urlparse(url)
    filename = Path(unquote(parsed.path)).name
    if not filename:
        return "document"

    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._")
    return stem or "document"


def _looks_like_html(payload: bytes) -> bool:
    sample = payload[:256].lstrip().lower()
    return sample.startswith(b"<!doctype html") or sample.startswith(b"<html")


def _validate_pdf_payload(payload: bytes, content_type: Optional[str]) -> None:
    if payload.startswith(_PDF_MAGIC):
        return
    if content_type and "pdf" in content_type.lower():
        raise DownloadError("Response claims PDF but payload does not start with %PDF- magic bytes")
    if _looks_like_html(payload):
        raise DownloadError("URL returned HTML instead of PDF")
    raise DownloadError("Downloaded payload is not a valid PDF")


def download_pdf(
    url: str,
    output_dir: Path,
    retries: int = 3,
    timeout_sec: float = 30.0,
) -> DownloadResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_basename_from_url(url)
    target_path = output_dir / (base_name + ".pdf")

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(follow_redirects=True, timeout=timeout_sec) as client:
                response = client.get(url)
            response.raise_for_status()
            payload = response.content
            _validate_pdf_payload(payload, response.headers.get("content-type"))
            target_path.write_bytes(payload)
            return DownloadResult(source_url=url, output_path=target_path, base_name=base_name)
        except (httpx.HTTPError, OSError, DownloadError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.6 * attempt)
                continue
            raise DownloadError("Failed to download PDF from %s: %s" % (url, exc)) from exc

    raise DownloadError("Failed to download PDF from %s: %s" % (url, last_error))
