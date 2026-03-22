from __future__ import annotations

import os
import sys
from pathlib import Path

import fitz
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def sample_pdf_path(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "sample.pdf"
    image_path = tmp_path / "figure.png"

    img = Image.new("RGB", (120, 80), color=(140, 170, 220))
    img.save(image_path)

    doc = fitz.open()

    page = doc.new_page()
    page.insert_text((72, 40), "Sample Header", fontsize=10)
    page.insert_text((72, 80), "1 Introduction", fontsize=16)
    page.insert_text(
        (72, 120),
        "This is a test paragraph for extraction and translation.",
        fontsize=11,
    )
    page.insert_text((72, 145), "E = mc^2 should remain unchanged.", fontsize=11)
    page.insert_text((72, 780), "Page Footer", fontsize=10)

    page = doc.new_page()
    page.insert_text((72, 40), "Sample Header", fontsize=10)
    page.insert_text((72, 80), "2 Methods", fontsize=16)
    page.insert_text(
        (72, 120),
        "We describe a second paragraph and include one image below.",
        fontsize=11,
    )
    page.insert_image(fitz.Rect(72, 160, 232, 250), filename=str(image_path))
    page.insert_text((72, 780), "Page Footer", fontsize=10)

    doc.save(pdf_path)
    doc.close()

    return pdf_path


@pytest.fixture
def scanned_like_pdf_path(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "scanned.pdf"
    image_path = tmp_path / "scan.png"

    img = Image.new("RGB", (420, 320), color=(250, 250, 250))
    for x in range(40, 380):
        img.putpixel((x, 80), (0, 0, 0))
    img.save(image_path)

    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(fitz.Rect(72, 120, 492, 440), filename=str(image_path))
    doc.save(pdf_path)
    doc.close()

    return pdf_path
