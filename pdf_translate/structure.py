"""Document structure inference from extracted page text."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import re
from typing import Dict, List, Optional

from .segmenter import segment_paragraph
from .text_normalize import normalize_text
from .types import DocumentModel, PageData, Section


_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)(?:\)|\.)?\s+[A-Za-z].*")
_HEADING_SYMBOL_RE = re.compile(r"[\[\]{}=<>≈+\-*/^_%]")
_BULLET_LINE_RE = re.compile(r"^\d+\.\s+\S")
_SUMPROD_LINE_END_RE = re.compile(r"(?:∑|∏)\s*[A-Za-z0-9]+\s*$")
_INDEX_LINE_START_RE = re.compile(r"^[A-Za-z]\s*=\s*[A-Za-z0-9+\-]")
_RELATION_END_RE = re.compile(r"[∈∉⊆⊂⊇=≠≤≥]\s*$")
_RELATION_START_RE = re.compile(r"^[A-Za-z0-9({\[]")
_FRACTION_LINE_END_RE = re.compile(r"\{[A-Za-z]\s*$")
_FRACTION_LINE_START_RE = re.compile(r"^[A-Za-z]\s*\|")
_FRONT_MATTER_LINE_RE = re.compile(
    r"(^cs\s*\d+$|^(spring|summer|fall|winter)\s+\d{4}$|course\s+notes|discrete\s+mathematics)",
    flags=re.IGNORECASE,
)
_TITLE_CONNECTOR_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "without",
}


def _page_nonempty_lines(page: PageData) -> List[str]:
    return [line.strip() for line in page.text.splitlines() if line.strip()]


def _normalize_repeat_key(line: str) -> str:
    normalized = line.lower()
    normalized = re.sub(r"\d+", "#", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _build_repeated_line_sets(pages: List[PageData]) -> Dict[str, set]:
    top_counter = Counter()
    bottom_counter = Counter()
    for page in pages:
        lines = _page_nonempty_lines(page)
        if not lines:
            continue
        for line in lines[:4]:
            top_counter[_normalize_repeat_key(line)] += 1
        for line in lines[-4:]:
            bottom_counter[_normalize_repeat_key(line)] += 1

    repeated_top = set(line for line, count in top_counter.items() if count >= 2)
    repeated_bottom = set(line for line, count in bottom_counter.items() if count >= 2)
    return {"top": repeated_top, "bottom": repeated_bottom}


def _clean_page_text(page: PageData, repeated_lines: Dict[str, set], symbol_fix_mode: str) -> str:
    normalized_text = normalize_text(page.text, mode=symbol_fix_mode)
    lines = [line.rstrip() for line in normalized_text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    while lines and _normalize_repeat_key(lines[0].strip()) in repeated_lines["top"]:
        lines.pop(0)
    while lines and _normalize_repeat_key(lines[-1].strip()) in repeated_lines["bottom"]:
        lines.pop()

    repaired = _repair_math_linebreaks(lines)
    return "\n".join(repaired).strip()


def _repair_math_linebreaks(lines: List[str]) -> List[str]:
    repaired: List[str] = []
    idx = 0
    while idx < len(lines):
        current = lines[idx].rstrip()
        if not current.strip():
            repaired.append(current)
            idx += 1
            continue

        while idx + 1 < len(lines):
            nxt = lines[idx + 1].strip()
            if not nxt:
                break
            if not _should_join_math_lines(current, nxt):
                break
            current = (current.rstrip() + " " + nxt).strip()
            idx += 1

        repaired.append(current)
        idx += 1
    return repaired


def _should_join_math_lines(left: str, right: str) -> bool:
    left_stripped = left.strip()
    right_stripped = right.strip()
    if not left_stripped or not right_stripped:
        return False

    if _SUMPROD_LINE_END_RE.search(left_stripped) and _INDEX_LINE_START_RE.search(right_stripped):
        return True

    if _RELATION_END_RE.search(left_stripped) and _RELATION_START_RE.search(right_stripped):
        return True

    if _FRACTION_LINE_END_RE.search(left_stripped) and _FRACTION_LINE_START_RE.search(right_stripped):
        return True

    return False


def _looks_title_with_connectors(text: str) -> bool:
    words = text.split()
    if not words:
        return False

    content_words = 0
    for word in words:
        cleaned = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", word)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in _TITLE_CONNECTOR_WORDS:
            continue
        content_words += 1
        if not (cleaned[0].isupper() or cleaned.isupper() or cleaned[0].isdigit()):
            return False
    return content_words >= 2


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    word_count = len(stripped.split())
    if len(stripped) > 100:
        return False
    if word_count > 10:
        return False
    if stripped.endswith((".", ",", ";", ":")):
        return False
    if _HEADING_SYMBOL_RE.search(stripped):
        return False
    if sum(1 for ch in stripped if ch.isalpha()) < 2:
        return False
    numbered = _NUMBERED_HEADING_RE.match(stripped)
    if numbered:
        token = numbered.group(1)
        try:
            if "." not in token and int(token) > 20:
                return False
        except ValueError:
            pass
        if word_count > 8:
            return False
        return True
    if stripped.isupper() and len(stripped.split()) <= 6:
        return True
    if _looks_title_with_connectors(stripped) and len(stripped.split()) <= 8:
        return True
    return False


def _heading_level(line: str) -> int:
    match = _NUMBERED_HEADING_RE.match(line.strip())
    if not match:
        return 1
    numbering = match.group(1)
    return numbering.count(".") + 1


def _is_front_matter_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return bool(_FRONT_MATTER_LINE_RE.search(stripped))


def _drop_front_matter_units(units: List[Dict[str, str]]) -> List[Dict[str, str]]:
    trimmed = list(units)
    while trimmed:
        unit = trimmed[0]
        if unit["type"] not in {"heading", "paragraph"}:
            break
        if not _is_front_matter_line(unit["text"]):
            break
        trimmed.pop(0)
    return trimmed


def _looks_like_bullet_continuation(line: str, previous_bullet: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("•"):
        return False
    if _BULLET_LINE_RE.match(stripped):
        return False
    if _is_heading(stripped):
        return False

    if previous_bullet.rstrip().endswith(("{", "[", "(", "=", ":", "|")):
        return True

    if re.match(r"^[A-Za-z]\s*[|=]", stripped):
        return True

    if stripped[0] in "{([|\\/":
        return True

    if stripped[0].islower():
        return True

    if len(stripped.split()) <= 8 and any(ch in stripped for ch in ["∈", "∉", "⊆", "⊂", "∩", "∪", "≠"]):
        return True

    return False


def _split_units(text: str) -> List[Dict[str, str]]:
    units: List[Dict[str, str]] = []
    current: List[str] = []

    def flush_paragraph() -> None:
        if current:
            units.append({"type": "paragraph", "text": " ".join(current).strip()})
            current[:] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            continue

        if "•" in line:
            flush_paragraph()
            for item in line.split("•"):
                cleaned = item.strip()
                if cleaned:
                    units.append({"type": "bullet", "text": cleaned})
            continue

        if _BULLET_LINE_RE.match(line):
            flush_paragraph()
            units.append({"type": "bullet", "text": line})
            continue

        if not current and units and units[-1]["type"] == "bullet":
            if _looks_like_bullet_continuation(line, units[-1]["text"]):
                units[-1]["text"] = (units[-1]["text"].rstrip() + " " + line).strip()
                continue

        if _is_heading(line):
            flush_paragraph()
            units.append({"type": "heading", "text": line})
            continue

        current.append(line)

    flush_paragraph()
    return units


def build_document_model(
    pages: List[PageData],
    source_url: str,
    title: Optional[str] = None,
    symbol_fix_mode: str = "conservative",
) -> DocumentModel:
    repeated_lines = _build_repeated_line_sets(pages)
    sections: List[Section] = []
    first_page_number = pages[0].page_number if pages else 1

    for page in pages:
        cleaned = _clean_page_text(page, repeated_lines, symbol_fix_mode=symbol_fix_mode)
        if not cleaned:
            continue

        units = _split_units(cleaned)
        if page.page_number == first_page_number:
            units = _drop_front_matter_units(units)
        for unit in units:
            block = unit["text"]
            if unit["type"] == "heading":
                sections.append(
                    Section(
                        heading=block,
                        level=_heading_level(block),
                        page_numbers=[page.page_number],
                    )
                )
                continue

            if unit["type"] == "bullet":
                block = "• " + block

            if not sections:
                sections.append(Section(heading="正文", level=1, page_numbers=[page.page_number]))

            current = sections[-1]
            if page.page_number not in current.page_numbers:
                current.page_numbers.append(page.page_number)
            current.paragraphs.append(segment_paragraph(block))

    if not sections:
        sections.append(Section(heading="正文", level=1))

    sections = [section for section in sections if section.paragraphs or section.images]
    if not sections:
        sections.append(Section(heading="正文", level=1))

    # Associate extracted images to the nearest section by page number.
    for page in pages:
        if not page.images:
            continue
        target_section = None
        for section in sections:
            if page.page_number in section.page_numbers:
                target_section = section
                break
        if target_section is None:
            target_section = sections[-1]
        target_section.images.extend(page.images)

    doc_title = title or sections[0].heading or "Translated Document"
    return DocumentModel(
        title=doc_title,
        source_url=source_url,
        generated_at=datetime.utcnow(),
        sections=sections,
    )
