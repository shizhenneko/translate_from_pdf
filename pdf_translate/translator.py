"""Translation adapters and document translation orchestration."""

from __future__ import annotations

import copy
import hashlib
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

from openai import OpenAI

from .errors import ConfigError, TranslateError
from .math_preserve import protect_math_fragments, restore_math_fragments
from .segmenter import is_math_like
from .text_normalize import normalize_text
from .types import DocumentModel, TranslateChunk

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert academic translator. Translate into Simplified Chinese in a literal style. "
    "Translate all natural-language English words into Chinese, including short words such as "
    "'non-zero', 'symbol', 'or', and 'as'. "
    "Preserve formulas, equations, mathematical symbols, variable names, and set notation exactly as-is. "
    "If the user text contains placeholders like [[MATH_0001]], keep them unchanged exactly. "
    "Do not leave standalone English words unless they are proper nouns or course identifiers. "
    "Do not add commentary. Return only translated text."
)
_TRANSLATION_POLICY_VERSION = "symbol-fix-v5"
_ENGLISH_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_ASCII_SENTENCE_PUNCT = ".,;:!?"
_CJK_SENTENCE_PUNCT = "。，；：！？"
_PUNCT_MAP = {
    ".": "。",
    ",": "，",
    ";": "；",
    ":": "：",
    "!": "！",
    "?": "？",
}
_RETRY_TRANSLATION_PREFIX = (
    "Strict rewrite task: translate all English prose to Simplified Chinese. "
    "Keep formulas and mathematical symbols unchanged. "
    "Keep placeholders like [[MATH_0001]] unchanged exactly. "
    "Return only rewritten text.\n\n"
)
_POST_EDIT_PREFIX = (
    "Post-edit task: keep existing Chinese and formulas unchanged, but translate every remaining English "
    "word/phrase/sentence into Simplified Chinese. "
    "Keep placeholders like [[MATH_0001]] unchanged exactly. "
    "Return only edited text.\n\n"
)
_PLACEHOLDER_RECOVERY_PREFIX = (
    "Critical formatting rule: preserve every placeholder token exactly, such as [[MATH_0001]], "
    "without deletion, renumbering, or edits. Then translate prose to Chinese and return only text.\n\n"
)


class BaseTranslator:
    def translate(self, text: str) -> str:
        raise NotImplementedError


class TranslationCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.cache_dir / (key + ".txt")

    def make_key(self, model: str, text: str, prompt_fingerprint: str = "") -> str:
        digest = hashlib.sha256(
            (model + "\n" + prompt_fingerprint + "\n" + text).encode("utf-8")
        ).hexdigest()
        return digest

    def get(self, key: str) -> Optional[str]:
        path = self._path(key)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def set(self, key: str, value: str) -> None:
        self._path(key).write_text(value, encoding="utf-8")


class LLMTranslator(BaseTranslator):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_attempts: int = 3,
        timeout_sec: float = 60.0,
        cache: Optional[TranslationCache] = None,
    ):
        if not api_key or not base_url or not model:
            raise ConfigError("LLM translator requires api_key, base_url, and model")

        self.model = model
        self.max_attempts = max_attempts
        self.cache = cache
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_sec)

    def _request(self, text: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        content = response.choices[0].message.content
        if content is None:
            raise TranslateError("LLM returned empty response content")
        return content.strip()

    def translate(self, text: str) -> str:
        cache_key = None
        prompt_fingerprint = hashlib.sha256(
            (_SYSTEM_PROMPT + "\n" + _TRANSLATION_POLICY_VERSION).encode("utf-8")
        ).hexdigest()[:16]
        if self.cache is not None:
            cache_key = self.cache.make_key(self.model, text, prompt_fingerprint=prompt_fingerprint)
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                translated = self._request(text)
                if self.cache is not None and cache_key is not None:
                    self.cache.set(cache_key, translated)
                return translated
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(0.8 * attempt)
                    continue
                raise TranslateError("Translation request failed: %s" % exc) from exc
        raise TranslateError("Translation request failed: %s" % last_error)


class FakeTranslator(BaseTranslator):
    def __init__(self, mapper: Optional[Callable[[str], str]] = None):
        self.mapper = mapper or (lambda text: "[ZH] " + text)

    def translate(self, text: str) -> str:
        return self.mapper(text)


def _should_translate_heading(heading: str) -> bool:
    stripped = heading.strip()
    if not stripped:
        return False
    if not re.search(r"[A-Za-z]", stripped):
        return False
    if is_math_like(stripped):
        return False
    if len(stripped) <= 3 and stripped.isupper():
        return False
    return True


def _collect_chunks(document: DocumentModel) -> List[TranslateChunk]:
    chunks: List[TranslateChunk] = []
    for sec_idx, section in enumerate(document.sections):
        for para_idx, paragraph in enumerate(section.paragraphs):
            for span_idx, span in enumerate(paragraph.spans):
                if span.translatable and span.text.strip():
                    chunks.append(
                        TranslateChunk(
                            section_index=sec_idx,
                            paragraph_index=para_idx,
                            span_index=span_idx,
                            text=span.text,
                        )
                    )
    return chunks


def _normalize_document_text(document: DocumentModel, symbol_fix_mode: str) -> None:
    document.title = normalize_text(document.title, mode=symbol_fix_mode)
    for section in document.sections:
        section.heading = normalize_text(section.heading, mode=symbol_fix_mode)
        for paragraph in section.paragraphs:
            for span in paragraph.spans:
                span.text = normalize_text(span.text, mode=symbol_fix_mode)


def _translate_with_math_preservation(
    text: str,
    *,
    translator: BaseTranslator,
    symbol_fix_mode: str,
    prefix: str = "",
) -> str:
    source_text = normalize_text(text, mode=symbol_fix_mode)
    protected, fragments = protect_math_fragments(source_text)
    request_text = prefix + protected

    translated = normalize_text(
        translator.translate(request_text),
        mode=symbol_fix_mode,
    )
    restored, missing, extras = restore_math_fragments(translated, fragments)
    if not missing and not extras:
        return restored

    recovered = normalize_text(
        translator.translate(_PLACEHOLDER_RECOVERY_PREFIX + request_text),
        mode=symbol_fix_mode,
    )
    restored_recovered, missing_recovered, extras_recovered = restore_math_fragments(recovered, fragments)
    if not missing_recovered and not extras_recovered:
        return restored_recovered

    logger.warning(
        "translate.placeholder_mismatch missing=%s extras=%s; fallback to source span",
        missing_recovered or missing,
        extras_recovered or extras,
    )
    return source_text


def _english_word_count(text: str) -> int:
    return len(_ENGLISH_WORD_RE.findall(text))


def _cjk_char_count(text: str) -> int:
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")


def _needs_quality_retry(source_text: str, translated_text: str) -> bool:
    if not translated_text.strip():
        return False
    if is_math_like(source_text):
        return False
    english_words = _english_word_count(translated_text)
    if english_words < 8:
        return False
    cjk_chars = _cjk_char_count(translated_text)
    return english_words > (cjk_chars // 3)


def _is_retry_better(initial_text: str, retried_text: str) -> bool:
    if not retried_text.strip():
        return False
    initial_english = _english_word_count(initial_text)
    retried_english = _english_word_count(retried_text)
    if retried_english < initial_english:
        return True
    if retried_english > initial_english:
        return False
    return _cjk_char_count(retried_text) >= _cjk_char_count(initial_text)


def _needs_residual_english_fix(source_text: str, translated_text: str) -> bool:
    if not translated_text.strip():
        return False
    if is_math_like(source_text):
        return False
    if _cjk_char_count(translated_text) <= 0:
        return False

    words = _ENGLISH_WORD_RE.findall(translated_text)
    if not words:
        return False
    # Uppercase abbreviations are often intentional (e.g., CS, PDF).
    return any(not word.isupper() for word in words)


def _restore_span_boundaries(source_text: str, translated_text: str) -> str:
    if not translated_text:
        return translated_text

    leading_ws_len = len(source_text) - len(source_text.lstrip())
    trailing_ws_len = len(source_text) - len(source_text.rstrip())
    leading_ws = source_text[:leading_ws_len]
    trailing_ws = source_text[len(source_text) - trailing_ws_len :] if trailing_ws_len else ""

    source_core = source_text.strip()
    translated_core = translated_text.strip()
    if not source_core or not translated_core:
        return leading_ws + translated_core + trailing_ws

    source_first = source_core[0]
    if source_first in _ASCII_SENTENCE_PUNCT and translated_core[0] not in (_ASCII_SENTENCE_PUNCT + _CJK_SENTENCE_PUNCT):
        translated_core = _PUNCT_MAP.get(source_first, source_first) + translated_core

    source_last = source_core[-1]
    if source_last in _ASCII_SENTENCE_PUNCT and translated_core[-1] not in (_ASCII_SENTENCE_PUNCT + _CJK_SENTENCE_PUNCT):
        translated_core = translated_core + _PUNCT_MAP.get(source_last, source_last)

    return leading_ws + translated_core + trailing_ws


def translate_document(
    document: DocumentModel,
    translator: BaseTranslator,
    max_concurrency: int = 1,
    symbol_fix_mode: str = "conservative",
) -> DocumentModel:
    """Translate translatable spans while preserving original span ordering."""

    translated_doc = copy.deepcopy(document)
    _normalize_document_text(translated_doc, symbol_fix_mode=symbol_fix_mode)

    for section in translated_doc.sections:
        if not _should_translate_heading(section.heading):
            continue
        section.heading = normalize_text(
            translator.translate(section.heading),
            mode=symbol_fix_mode,
        )

    chunks = _collect_chunks(translated_doc)
    if not chunks:
        return translated_doc

    results: List[Tuple[int, str]] = []

    def _job(index_chunk: Tuple[int, TranslateChunk]) -> Tuple[int, str]:
        index, chunk = index_chunk
        source_text = normalize_text(chunk.text, mode=symbol_fix_mode)
        translated_text = _translate_with_math_preservation(
            source_text,
            translator=translator,
            symbol_fix_mode=symbol_fix_mode,
        )
        if isinstance(translator, LLMTranslator) and _needs_quality_retry(source_text, translated_text):
            retried = _translate_with_math_preservation(
                source_text,
                translator=translator,
                symbol_fix_mode=symbol_fix_mode,
                prefix=_RETRY_TRANSLATION_PREFIX,
            )
            if _is_retry_better(translated_text, retried):
                translated_text = retried
            for _ in range(2):
                if not _needs_quality_retry(source_text, translated_text):
                    break
                post_edited = _translate_with_math_preservation(
                    translated_text,
                    translator=translator,
                    symbol_fix_mode=symbol_fix_mode,
                    prefix=_POST_EDIT_PREFIX,
                )
                if not _is_retry_better(translated_text, post_edited):
                    break
                translated_text = post_edited
        if isinstance(translator, LLMTranslator) and _needs_residual_english_fix(source_text, translated_text):
            post_edited = _translate_with_math_preservation(
                translated_text,
                translator=translator,
                symbol_fix_mode=symbol_fix_mode,
                prefix=_POST_EDIT_PREFIX,
            )
            if _is_retry_better(translated_text, post_edited):
                translated_text = post_edited
        translated_text = _restore_span_boundaries(source_text, translated_text)
        return index, translated_text

    indexed_chunks = list(enumerate(chunks))
    if max_concurrency <= 1:
        for indexed in indexed_chunks:
            results.append(_job(indexed))
    else:
        with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
            for result in pool.map(_job, indexed_chunks):
                results.append(result)

    results_map = dict(results)
    for idx, chunk in enumerate(chunks):
        translated_text = results_map[idx]
        section = translated_doc.sections[chunk.section_index]
        paragraph = section.paragraphs[chunk.paragraph_index]
        paragraph.spans[chunk.span_index].text = translated_text

    return translated_doc
