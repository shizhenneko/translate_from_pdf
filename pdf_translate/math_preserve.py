"""Utilities for protecting math fragments through translation and rendering."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Sequence, Tuple

_MATH_TOKEN_RE = re.compile(r"\[\[MATH_\d{4}\]\]")
_WHITESPACE_RE = re.compile(r"[ \t\r\n\f\v]+")
_ENGLISH_WORD_RE = re.compile(r"[A-Za-z]{3,}")

_SUM_PRODUCT_RE = re.compile(
    r"(?:"
    r"(?:∑|∏)\s*[A-Za-z0-9]+"
    r"(?:\s*[A-Za-z]\s*=\s*[A-Za-z0-9+\-]+)"
    r"(?:\s*[A-Za-z0-9()^]+)?"
    r"(?:\s*=\s*[A-Za-z0-9·+\-^()\s]+)?"
    r")"
)
_SET_BUILDER_RE = re.compile(r"\{[^{}\n]{0,140}\|[^{}\n]{0,180}\}")
_SET_LITERAL_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*\s*=\s*\{[A-Za-z0-9,\s+\-*/^._]{1,160}\}")
_RELATION_RE = re.compile(
    r"(?:[A-Za-z0-9()\\+\-]+)\s*(?:∈|∉|⊆|⊂|⊇|=|≠|≤|≥)\s*(?:[A-Za-z0-9()\\+\-]+)"
)
_UNION_INTERSECTION_RE = re.compile(
    r"(?:[A-Za-z0-9{}()\\]+(?:\s*[∩∪\\]\s*[A-Za-z0-9{}()\\]+){1,}\s*(?:=|≠)\s*[A-Za-z0-9{}()\\∅]+)"
)
_SUM_PRODUCT_LAYOUT_RE = re.compile(
    r"^([∑∏])\s*([A-Za-z0-9()+\-]+)\s+([A-Za-z]\s*=\s*[A-Za-z0-9+\-]+)\s+(.+)$"
)
_LETTER_POWER2_RE = re.compile(r"([A-Za-z])2\b")
_DIGIT_POWER2_RE = re.compile(r"(?<![0-9])([0-9])2(?=\s*(?:[+\-·]|$|=))")
_INLINE_LETTER_POWER2_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z])2(?=\s*(?:[+\-*/=),.;]|$))")
_SET_FRACTION_RE = re.compile(r"\{\s*([A-Za-z])\s+([A-Za-z])\s+\|")

_CANDIDATE_PATTERNS: Sequence[Tuple[str, re.Pattern]] = (
    ("sum_product", _SUM_PRODUCT_RE),
    ("set_builder", _SET_BUILDER_RE),
    ("set_literal", _SET_LITERAL_RE),
    ("union_intersection", _UNION_INTERSECTION_RE),
    ("relation", _RELATION_RE),
)

_MATH_SIGNAL_CHARS = set("∑∏∈∉⊆⊂⊇∩∪=≠≤≥{}|\\^·")


@dataclass(frozen=True)
class MathSpan:
    start: int
    end: int
    text: str
    kind: str


@dataclass(frozen=True)
class MathFragment:
    token: str
    text: str
    kind: str


def has_sum_or_product(text: str) -> bool:
    return ("∑" in text) or ("∏" in text)


def find_math_spans(text: str) -> List[MathSpan]:
    if not text:
        return []

    candidates: List[MathSpan] = []
    for kind, pattern in _CANDIDATE_PATTERNS:
        for match in pattern.finditer(text):
            matched_text = match.group(0)
            compact = matched_text.strip()
            if len(compact) < 3:
                continue
            if _math_signal_score(compact) < 2:
                continue
            if not _should_keep_candidate(kind, compact):
                continue
            candidates.append(
                MathSpan(
                    start=match.start(),
                    end=match.end(),
                    text=matched_text,
                    kind=kind,
                )
            )
    if not candidates:
        return []
    return _select_non_overlapping_spans(candidates)


def protect_math_fragments(text: str) -> Tuple[str, List[MathFragment]]:
    spans = find_math_spans(text)
    if not spans:
        return text, []

    fragments: List[MathFragment] = []
    parts: List[str] = []
    cursor = 0

    for index, span in enumerate(spans, 1):
        token = "[[MATH_%04d]]" % index
        parts.append(text[cursor : span.start])
        parts.append(token)
        fragments.append(MathFragment(token=token, text=span.text, kind=span.kind))
        cursor = span.end

    parts.append(text[cursor:])
    return "".join(parts), fragments


def restore_math_fragments(text: str, fragments: Sequence[MathFragment]) -> Tuple[str, List[str], List[str]]:
    if not fragments:
        return text, [], []

    restored = text
    missing: List[str] = []
    expected = {fragment.token for fragment in fragments}

    for fragment in fragments:
        if fragment.token not in restored:
            missing.append(fragment.token)
            continue
        restored = restored.replace(fragment.token, fragment.text)

    extras = [token for token in _MATH_TOKEN_RE.findall(restored) if token not in expected]
    return restored, missing, extras


def stabilize_math_layout(text: str) -> str:
    if not text:
        return text

    protected, fragments = protect_math_fragments(text)
    if not fragments:
        repaired = _repair_set_builder_fraction(text)
        return _repair_inline_square_powers(repaired)

    token_to_formatted: Dict[str, str] = {}
    for fragment in fragments:
        formatted = _normalize_math_whitespace(fragment.text)
        if fragment.kind == "sum_product":
            formatted = _normalize_sum_product_notation(formatted)
            formatted = _repair_missing_square_powers(formatted)
        if fragment.kind == "set_builder":
            formatted = _repair_set_builder_fraction(formatted)
        formatted = _tie_relation_operators(formatted)
        if has_sum_or_product(formatted):
            formatted = formatted.replace(" ", "\u00a0")
        token_to_formatted[fragment.token] = formatted

    stabilized = protected
    for fragment in fragments:
        stabilized = stabilized.replace(fragment.token, token_to_formatted[fragment.token])
    stabilized = _repair_set_builder_fraction(stabilized)
    return _repair_inline_square_powers(stabilized)


def _select_non_overlapping_spans(candidates: Sequence[MathSpan]) -> List[MathSpan]:
    ordered = sorted(candidates, key=lambda span: (span.start, -(span.end - span.start)))
    selected: List[MathSpan] = []
    for span in ordered:
        if not selected:
            selected.append(span)
            continue

        last = selected[-1]
        overlaps = span.start < last.end
        if not overlaps:
            selected.append(span)
            continue

        if _span_priority(span) > _span_priority(last):
            selected[-1] = span
    return selected


def _math_signal_score(text: str) -> int:
    return sum(1 for ch in text if ch in _MATH_SIGNAL_CHARS)


def _span_priority(span: MathSpan) -> Tuple[int, int]:
    length = span.end - span.start
    signal = _math_signal_score(span.text)
    return (signal, length)


def _should_keep_candidate(kind: str, text: str) -> bool:
    if kind != "set_builder":
        return True
    # If a set-builder chunk contains prose words, let the translator process
    # the prose and preserve only symbol-heavy fragments via other patterns.
    return len(_ENGLISH_WORD_RE.findall(text)) < 2


def _normalize_math_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _normalize_sum_product_notation(text: str) -> str:
    match = _SUM_PRODUCT_LAYOUT_RE.match(text)
    if not match:
        return text

    symbol = match.group(1)
    upper = match.group(2).strip()
    index = re.sub(r"\s+", "", match.group(3))
    body = match.group(4).strip()
    return "%s_{%s}^{%s} %s" % (symbol, index, upper, body)


def _repair_missing_square_powers(text: str) -> str:
    repaired = _LETTER_POWER2_RE.sub(r"\1^2", text)
    repaired = _DIGIT_POWER2_RE.sub(r"\1^2", repaired)
    return repaired


def _repair_set_builder_fraction(text: str) -> str:
    lowered = text.lower()
    if "integers" not in lowered and "∈z" not in lowered and "有理数" not in text:
        return text
    return _SET_FRACTION_RE.sub(r"{\1/\2 |", text)


def _repair_inline_square_powers(text: str) -> str:
    if not text:
        return text
    if not any(signal in text for signal in ("=", "+", "-", "−", "∑", "∏", "∀", "∃")):
        return text

    repaired = _INLINE_LETTER_POWER2_RE.sub(r"\1^2", text)
    if "···" in repaired or has_sum_or_product(repaired):
        repaired = _DIGIT_POWER2_RE.sub(r"\1^2", repaired)
    return repaired


def _tie_relation_operators(text: str) -> str:
    # Keep operands visually attached to relation operators to reduce awkward wraps.
    # Preserve original spacing style whenever possible.
    relation_ops = "∈∉⊆⊂⊇=≠≤≥"
    pattern = r"([A-Za-z0-9)\]}])(\s*)([%s])(\s*)([A-Za-z0-9({\[])" % relation_ops

    def _repl(match: re.Match) -> str:
        left = match.group(1)
        left_ws = match.group(2)
        op = match.group(3)
        right_ws = match.group(4)
        right = match.group(5)
        tied_left = "\u00a0" if left_ws else ""
        tied_right = "\u00a0" if right_ws else ""
        return "%s%s%s%s%s" % (left, tied_left, op, tied_right, right)

    return re.sub(pattern, _repl, text)
