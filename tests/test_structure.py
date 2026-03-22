from __future__ import annotations

from pdf_translate.extractor import extract_pdf
from pdf_translate.structure import build_document_model
from pdf_translate.types import PageData


def test_structure_detects_headings(sample_pdf_path):
    pages = extract_pdf(sample_pdf_path)
    doc = build_document_model(pages, source_url="https://example.com/sample.pdf")

    headings = [section.heading for section in doc.sections]
    assert any("Introduction" in h for h in headings)
    assert any("Methods" in h for h in headings)


def test_structure_removes_repeated_header_footer(sample_pdf_path):
    pages = extract_pdf(sample_pdf_path)
    doc = build_document_model(pages, source_url="https://example.com/sample.pdf")

    body_text = "\n".join(
        paragraph.text()
        for section in doc.sections
        for paragraph in section.paragraphs
    )
    assert "Sample Header" not in body_text
    assert "Page Footer" not in body_text


def test_structure_associates_images_to_sections(sample_pdf_path):
    pages = extract_pdf(sample_pdf_path)
    doc = build_document_model(pages, source_url="https://example.com/sample.pdf")

    total_images = sum(len(section.images) for section in doc.sections)
    assert total_images >= 1


def test_structure_merges_bullet_continuation_and_removes_front_matter():
    raw = "\n".join(
        [
            "CS 70",
            "Spring 2026",
            "Course Notes",
            "Note 0",
            "Some Important Sets",
            "• Q denotes the set of all rational numbers: {a",
            "b | a,b ∈Z, b ̸= 0}.",
        ]
    )
    pages = [PageData(page_number=1, raw_text=raw, text=raw, text_len=len(raw), used_ocr=False, images=[])]
    doc = build_document_model(pages, source_url="https://example.com/n0.pdf")

    headings = [section.heading for section in doc.sections]
    assert "Course Notes" not in headings
    assert any("Some Important Sets" in heading for heading in headings)

    all_paragraphs = [paragraph.text() for section in doc.sections for paragraph in section.paragraphs]
    assert any("Q denotes the set of all rational numbers: {a b | a,b ∈Z, b ≠ 0}." in text for text in all_paragraphs)


def test_structure_repairs_math_linebreaks_for_sum_and_relations():
    raw = "\n".join(
        [
            "Mathematical Notation",
            "We write ∑n",
            "i=1 i.",
            "If x ∈",
            "A, then we continue.",
        ]
    )
    pages = [PageData(page_number=1, raw_text=raw, text=raw, text_len=len(raw), used_ocr=False, images=[])]
    doc = build_document_model(pages, source_url="https://example.com/n0.pdf")

    all_paragraphs = [paragraph.text() for section in doc.sections for paragraph in section.paragraphs]
    merged_text = "\n".join(all_paragraphs)
    assert "∑n i=1 i" in merged_text
    assert "x ∈ A" in merged_text
