"""Shared data models for the translation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class ImageAsset:
    page_number: int
    image_id: str
    ext: str
    data: bytes


@dataclass
class PageData:
    page_number: int
    raw_text: str
    text: str
    text_len: int
    used_ocr: bool = False
    images: List[ImageAsset] = field(default_factory=list)


@dataclass
class Span:
    text: str
    translatable: bool


@dataclass
class Paragraph:
    spans: List[Span] = field(default_factory=list)

    def text(self) -> str:
        return "".join(span.text for span in self.spans)


@dataclass
class Section:
    heading: str
    level: int
    paragraphs: List[Paragraph] = field(default_factory=list)
    page_numbers: List[int] = field(default_factory=list)
    images: List[ImageAsset] = field(default_factory=list)


@dataclass
class DocumentModel:
    title: str
    source_url: str
    generated_at: datetime
    sections: List[Section] = field(default_factory=list)


@dataclass
class TranslateChunk:
    section_index: int
    paragraph_index: int
    span_index: int
    text: str


@dataclass
class MarkdownChunk:
    index: int
    text: str


@dataclass
class PipelineResult:
    downloaded_pdf: Path
    output_markdown: Path
    page_count: int
    section_count: int
    job_id: str = ""
    input_pdf: Optional[Path] = None
    marker_markdown: Optional[Path] = None
    translated_markdown: Optional[Path] = None
    status: str = ""
    stage: str = ""
    error: Optional[str] = None
