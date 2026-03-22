"""Normalization helpers for extracted/translated text."""

from __future__ import annotations

import re
from typing import Iterable

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PRIVATE_USE_RE = re.compile(r"[\ue000-\uf8ff]")
_SLASH_NOT_IN_RE = re.compile(r"(?<![0-9A-Za-z])/\s*∈")
_COMBINING_NOT_EQUAL_RE = re.compile(r"\u0338\s*=")
_EMPTY_SET_TOKEN_RE = re.compile(r"(?<![0-9A-Za-z])/\s*0(?![0-9A-Za-z])")
_EMPTY_SET_CONTEXT_RE = re.compile(
    r"(∩|∪|⊂|⊆|⊇|∈|∉|\\|{}|"
    r"empty\s+set|subset|superset|set\s+difference|set\s+notation|"
    r"空集|集合|子集|并集|交集|补集)",
    flags=re.IGNORECASE,
)

_SYMBOL_FIX_MODES = {"off", "conservative"}
_PRIVATE_USE_TRANSLATION_TABLE = str.maketrans(
    {
        "\uf8f1": "{",
        "\uf8f2": "|",
        "\uf8f3": "}",
        "\uf8f4": "|",
    }
)


def allowed_symbol_fix_modes() -> Iterable[str]:
    return tuple(sorted(_SYMBOL_FIX_MODES))


def normalize_text(text: str, mode: str = "conservative") -> str:
    """Normalize control characters and common symbol artifacts.

    Parameters
    ----------
    text:
        Raw text to normalize.
    mode:
        Symbol-repair policy. Supported values: ``off``, ``conservative``.
    """

    if not text:
        return text

    cleaned = _CONTROL_CHAR_RE.sub("", text)
    cleaned = cleaned.translate(_PRIVATE_USE_TRANSLATION_TABLE)
    cleaned = _PRIVATE_USE_RE.sub("", cleaned)
    if mode == "off":
        return cleaned
    if mode not in _SYMBOL_FIX_MODES:
        raise ValueError("Unsupported symbol fix mode: %s" % mode)

    cleaned = _SLASH_NOT_IN_RE.sub("∉", cleaned)
    cleaned = _COMBINING_NOT_EQUAL_RE.sub("≠", cleaned)
    cleaned = _replace_empty_set_tokens(cleaned)
    return cleaned


def count_control_chars(text: str) -> int:
    if not text:
        return 0
    return len(_CONTROL_CHAR_RE.findall(text))


def _replace_empty_set_tokens(text: str) -> str:
    def _repl(match: re.Match) -> str:
        start = max(0, match.start() - 48)
        end = min(len(text), match.end() + 48)
        window = text[start:end]
        if _EMPTY_SET_CONTEXT_RE.search(window):
            return "∅"
        return match.group(0)

    return _EMPTY_SET_TOKEN_RE.sub(_repl, text)
