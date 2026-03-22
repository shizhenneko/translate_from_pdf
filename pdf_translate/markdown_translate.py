"""Markdown-first translation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, List, Tuple

from .text_normalize import normalize_text
from .translator import BaseTranslator
from .types import MarkdownChunk

_FENCE_RE = re.compile(r"```.*?```", re.S)
_DISPLAY_MATH_RE = re.compile(r"\$\$.*?\$\$", re.S)
_INLINE_MATH_RE = re.compile(r"(?<!\$)\$[^$\n]+\$(?!\$)")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\([^)]+\)")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_URL_RE = re.compile(r"https?://[^\s)>\]]+")
_PLACEHOLDER_RE = re.compile(r"\[\[[A-Z_]+_\d{4}\]\]")


@dataclass
class _ProtectedFragment:
    token: str
    value: str


def _protect_patterns(text: str) -> Tuple[str, List[_ProtectedFragment]]:
    patterns = [
        ("FENCE", _FENCE_RE),
        ("DISPLAY_MATH", _DISPLAY_MATH_RE),
        ("IMAGE", _IMAGE_RE),
        ("LINK", _LINK_RE),
        ("INLINE_MATH", _INLINE_MATH_RE),
        ("INLINE_CODE", _INLINE_CODE_RE),
        ("URL", _URL_RE),
    ]
    protected = text
    fragments: List[_ProtectedFragment] = []

    for label, pattern in patterns:
        def repl(match: re.Match) -> str:
            token = "[[%s_%04d]]" % (label, len(fragments))
            fragments.append(_ProtectedFragment(token=token, value=match.group(0)))
            return token

        protected = pattern.sub(repl, protected)
    return protected, fragments


def _restore_patterns(text: str, fragments: Iterable[_ProtectedFragment]) -> str:
    restored = text
    for fragment in fragments:
        restored = restored.replace(fragment.token, fragment.value)
    return restored


def _placeholder_intact(text: str, fragments: Iterable[_ProtectedFragment]) -> bool:
    return all(fragment.token in text for fragment in fragments)


def _split_blocks(markdown_text: str) -> List[str]:
    lines = markdown_text.splitlines()
    blocks: List[str] = []
    current: List[str] = []
    in_fence = False

    def flush() -> None:
        if current:
            block = "\n".join(current).strip("\n")
            if block:
                blocks.append(block)
            current[:] = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if not in_fence:
                flush()
                in_fence = True
                current.append(line)
                continue
            current.append(line)
            flush()
            in_fence = False
            continue

        if in_fence:
            current.append(line)
            continue

        if not stripped:
            flush()
            continue

        if stripped.startswith("#"):
            flush()
            blocks.append(line)
            continue

        if re.match(r"^([-*]|\d+\.)\s+", stripped):
            flush()
            blocks.append(line)
            continue

        if stripped.startswith("!["):
            flush()
            blocks.append(line)
            continue

        if stripped.startswith("|"):
            flush()
            blocks.append(line)
            continue

        current.append(line)

    flush()
    return blocks


def chunk_markdown(markdown_text: str, max_chars: int = 4000) -> List[MarkdownChunk]:
    blocks = _split_blocks(markdown_text)
    if not blocks:
        return [MarkdownChunk(index=0, text="")]

    chunks: List[MarkdownChunk] = []
    current: List[str] = []
    current_len = 0

    for block in blocks:
        block_len = len(block)
        block_is_heading = block.lstrip().startswith("#")
        if block_is_heading and current:
            chunks.append(MarkdownChunk(index=len(chunks), text="\n\n".join(current)))
            current = []
            current_len = 0

        prospective_len = current_len + block_len + (2 if current else 0)
        if current and prospective_len > max_chars:
            chunks.append(MarkdownChunk(index=len(chunks), text="\n\n".join(current)))
            current = [block]
            current_len = block_len
            continue

        current.append(block)
        current_len = prospective_len

    if current:
        chunks.append(MarkdownChunk(index=len(chunks), text="\n\n".join(current)))

    return chunks


def translate_markdown(
    markdown_text: str,
    *,
    translator: BaseTranslator,
    max_chunk_chars: int = 4000,
    symbol_fix_mode: str = "conservative",
) -> str:
    translated_chunks: List[str] = []

    for chunk in chunk_markdown(markdown_text, max_chars=max_chunk_chars):
        normalized = normalize_text(chunk.text, mode=symbol_fix_mode)
        protected, fragments = _protect_patterns(normalized)
        translated = normalize_text(
            translator.translate(protected),
            mode=symbol_fix_mode,
        )
        if not _placeholder_intact(translated, fragments):
            translated_chunks.append(chunk.text)
            continue
        translated_chunks.append(_restore_patterns(translated, fragments))

    return "\n\n".join(part for part in translated_chunks if part != "")


def translate_markdown_file(
    input_path: Path,
    output_path: Path,
    *,
    translator: BaseTranslator,
    max_chunk_chars: int = 4000,
    symbol_fix_mode: str = "conservative",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    translated = translate_markdown(
        input_path.read_text(encoding="utf-8"),
        translator=translator,
        max_chunk_chars=max_chunk_chars,
        symbol_fix_mode=symbol_fix_mode,
    )
    output_path.write_text(translated, encoding="utf-8")
    return output_path
