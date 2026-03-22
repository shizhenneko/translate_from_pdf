"""Paragraph segmentation and math/code passthrough detection."""

from __future__ import annotations

import re
from typing import Iterable, List

from .math_preserve import find_math_spans
from .text_normalize import normalize_text
from .types import Paragraph, Span

_INLINE_SPECIAL_RE = re.compile(r"(\$[^$]+\$|\\\([^\)]+\\\)|\\\[[^\]]+\\\]|`[^`]+`)")
_MATH_CHARS = set("=+-*/^_<>|()[]{}\\")
_GREEK_OR_LATEX_RE = re.compile(r"(\\[a-zA-Z]+|[α-ωΑ-Ω])")
_MATH_SYMBOL_RE = re.compile(r"[∑∏√∞≈≤≥≠∈∉⊂⊆∪∩∀∃]")
_WORD_RE = re.compile(r"[A-Za-z]+")
_CONNECTOR_RE = re.compile(r"\b(?:as|or|and)\b", re.IGNORECASE)
_TEXTUAL_HYPHEN_RE = re.compile(r"^[A-Za-z]{2,}\s*-\s*[A-Za-z]{2,}$")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?。！？])\s+")
_INLINE_EQUATION_RE = re.compile(
    r"("
    r"\|[^|\n]{1,40}\|"
    r"|"
    r"(?:[∑∏]\s*[A-Za-z0-9]+\s*[A-Za-z]\s*=\s*[A-Za-z0-9+\-]+\s*[A-Za-z0-9()^]*)"
    r"|"
    r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*(?:\{[^{}\n]{1,80}\}|[A-Za-z0-9_(){}\[\]\\.^]+(?:\s*[+\-*/^]\s*[A-Za-z0-9_(){}\[\]\\.^]+){0,8})"
    r"|"
    r"\b(?:[A-Za-z0-9_]+(?:\s*[+\-*/^]\s*[A-Za-z0-9_]+){1,})\b"
    r")"
)


def is_math_like(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    if stripped.startswith("$") and stripped.endswith("$"):
        return True

    math_count = sum(1 for ch in stripped if ch in _MATH_CHARS)
    symbol_count = len(_MATH_SYMBOL_RE.findall(stripped))
    words = _WORD_RE.findall(stripped)
    alpha_count = sum(len(word) for word in words)
    word_count = len(words)
    token_count = len(stripped.split())
    ratio = float(math_count) / float(max(len(stripped), 1))

    # Prose-heavy fragments should remain translatable even if they contain a few symbols.
    if len(stripped) >= 60 and word_count >= 8 and alpha_count >= 24:
        return False

    if word_count >= 1 and any(ch in stripped for ch in ".?!") and (math_count + symbol_count) <= 3:
        return False

    if _GREEK_OR_LATEX_RE.search(stripped) and token_count <= 16:
        return True

    if token_count <= 8 and (math_count + symbol_count) >= 3 and ratio >= 0.18:
        return True

    if token_count <= 6 and "=" in stripped and (math_count + symbol_count) >= 2 and alpha_count <= 20:
        return True

    if word_count <= 2 and (math_count + symbol_count) >= 2:
        return True

    return False


def _split_equation_fragments(text: str) -> List[str]:
    fragments = _INLINE_EQUATION_RE.split(text)
    return [fragment for fragment in fragments if fragment]


def _is_formulaish_fragment(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if is_math_like(stripped):
        return True
    if _MATH_SYMBOL_RE.search(stripped):
        return True
    return any(ch in stripped for ch in "=+-*/^_{}[]()\\|")


def _should_force_translatable(fragment: str) -> bool:
    stripped = fragment.strip()
    lowered = stripped.lower()
    if not stripped:
        return False

    if _TEXTUAL_HYPHEN_RE.fullmatch(stripped):
        return True
    if lowered.startswith("symbol ") or lowered.startswith("denoted by "):
        return True

    words = _WORD_RE.findall(stripped)
    if any(len(word) >= 4 for word in words):
        symbol_count = sum(1 for ch in stripped if ch in _MATH_CHARS) + len(_MATH_SYMBOL_RE.findall(stripped))
        if symbol_count <= 2:
            return True

    return False


def _split_formula_with_connectors(fragment: str) -> List[Span]:
    if not _CONNECTOR_RE.search(fragment):
        return []
    if not is_math_like(fragment) and not _INLINE_EQUATION_RE.fullmatch(fragment):
        return []

    pieces = re.split(r"(\b(?:as|or|and)\b)", fragment, flags=re.IGNORECASE)
    spans: List[Span] = []
    for piece in pieces:
        if not piece:
            continue
        if _CONNECTOR_RE.fullmatch(piece):
            spans.append(Span(text=piece, translatable=True))
            continue
        spans.append(Span(text=piece, translatable=not _is_formulaish_fragment(piece)))

    if len(spans) < 2:
        return []
    if not any(span.translatable for span in spans):
        return []
    if not any(not span.translatable for span in spans):
        return []
    return spans


def _split_detected_math_fragments(text: str) -> List[Span]:
    detected = find_math_spans(text)
    if not detected:
        return [Span(text=text, translatable=not is_math_like(text))]

    spans: List[Span] = []
    cursor = 0
    for match in detected:
        if match.start > cursor:
            head = text[cursor : match.start]
            if head:
                spans.append(Span(text=head, translatable=not is_math_like(head)))
        spans.append(Span(text=match.text, translatable=False))
        cursor = match.end

    tail = text[cursor:]
    if tail:
        spans.append(Span(text=tail, translatable=not is_math_like(tail)))
    return spans


def _split_long_translatable_fragment(text: str, max_len: int = 260) -> List[str]:
    stripped = text.strip()
    if len(stripped) <= max_len:
        return [text]
    if is_math_like(text):
        return [text]

    parts = _SENTENCE_BOUNDARY_RE.split(text)
    if len(parts) <= 1:
        return [text]

    chunks: List[str] = []
    current = ""
    for part in parts:
        if not part:
            continue
        candidate = (current + " " + part).strip() if current else part.strip()
        if current and len(candidate) > max_len:
            chunks.append(current)
            current = part.strip()
        else:
            current = candidate
    if current:
        chunks.append(current)

    if len(chunks) <= 1:
        return [text]
    return chunks


def segment_paragraph(text: str) -> Paragraph:
    normalized = normalize_text(text)
    pieces = _INLINE_SPECIAL_RE.split(normalized)
    spans: List[Span] = []
    for part in pieces:
        if part is None or part == "":
            continue

        is_special = bool(_INLINE_SPECIAL_RE.fullmatch(part))
        if is_special:
            spans.append(Span(text=part, translatable=False))
            continue

        for fragment in _split_equation_fragments(part):
            if not fragment:
                continue

            connector_split = _split_formula_with_connectors(fragment)
            if connector_split:
                spans.extend(connector_split)
                continue

            for sub in _split_detected_math_fragments(fragment):
                if not sub.text:
                    continue
                if not sub.translatable:
                    spans.append(sub)
                    continue

                if _INLINE_EQUATION_RE.fullmatch(sub.text):
                    force_translatable = _should_force_translatable(sub.text)
                    if force_translatable:
                        for split_piece in _split_long_translatable_fragment(sub.text):
                            spans.append(Span(text=split_piece, translatable=True))
                    else:
                        spans.append(Span(text=sub.text, translatable=False))
                    continue

                translatable = not is_math_like(sub.text)
                if translatable:
                    for split_piece in _split_long_translatable_fragment(sub.text):
                        spans.append(Span(text=split_piece, translatable=True))
                else:
                    spans.append(Span(text=sub.text, translatable=False))

    if not spans:
        spans.append(Span(text=normalized, translatable=not is_math_like(normalized)))
    return Paragraph(spans=spans)


def segment_paragraphs(paragraphs: Iterable[str]) -> List[Paragraph]:
    return [segment_paragraph(p) for p in paragraphs if p.strip()]
