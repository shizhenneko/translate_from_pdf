from __future__ import annotations

import httpx
import pytest
import respx

from pdf_translate.downloader import download_pdf, sanitize_basename_from_url
from pdf_translate.errors import DownloadError


_VALID_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


def test_sanitize_basename_from_url_basic():
    assert sanitize_basename_from_url("https://a/b/n14.pdf") == "n14"
    assert sanitize_basename_from_url("https://a/b/hello%20world.pdf") == "hello-world"
    assert sanitize_basename_from_url("https://a/") == "document"


@respx.mock
def test_download_pdf_success(tmp_path):
    respx.get("https://example.com/doc.pdf").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=_VALID_PDF_BYTES,
        )
    )

    result = download_pdf("https://example.com/doc.pdf", output_dir=tmp_path)

    assert result.base_name == "doc"
    assert result.output_path.exists()
    assert result.output_path.read_bytes().startswith(b"%PDF-")


@respx.mock
def test_download_pdf_rejects_html(tmp_path):
    respx.get("https://example.com/not.pdf").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<html><body>error</body></html>",
        )
    )

    with pytest.raises(DownloadError):
        download_pdf("https://example.com/not.pdf", output_dir=tmp_path)


@respx.mock
def test_download_pdf_retries_and_succeeds(tmp_path):
    route = respx.get("https://example.com/retry.pdf")
    route.side_effect = [
        httpx.ConnectError("boom"),
        httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=_VALID_PDF_BYTES,
        ),
    ]

    result = download_pdf("https://example.com/retry.pdf", output_dir=tmp_path, retries=2)

    assert result.output_path.exists()
    assert route.call_count == 2
