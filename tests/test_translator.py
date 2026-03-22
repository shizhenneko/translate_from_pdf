from __future__ import annotations

import time

import pytest

from pdf_translate.errors import ConfigError, TranslateError
from pdf_translate.translator import (
    _is_retry_better,
    _needs_residual_english_fix,
    _needs_quality_retry,
    _restore_span_boundaries,
    FakeTranslator,
    LLMTranslator,
    TranslationCache,
    translate_document,
)
from pdf_translate.types import DocumentModel, Paragraph, Section, Span


def _doc_for_translation() -> DocumentModel:
    return DocumentModel(
        title="T",
        source_url="https://example.com",
        generated_at=None,
        sections=[
            Section(
                heading="1 Intro",
                level=1,
                paragraphs=[
                    Paragraph(spans=[Span("Hello world", True), Span(" E = mc^2 ", False)]),
                    Paragraph(spans=[Span("Another paragraph", True)]),
                ],
            )
        ],
    )


def test_fake_translator_maps_text():
    tr = FakeTranslator(lambda t: "ZH:" + t)
    assert tr.translate("abc") == "ZH:abc"


def test_translation_cache_roundtrip(tmp_path):
    cache = TranslationCache(tmp_path)
    key = cache.make_key("m", "hello")
    assert cache.get(key) is None
    cache.set(key, "你好")
    assert cache.get(key) == "你好"


def test_translate_document_preserves_passthrough_spans():
    doc = _doc_for_translation()
    translated = translate_document(doc, FakeTranslator(lambda t: "ZH:" + t), max_concurrency=1)

    assert translated.sections[0].heading.startswith("ZH:")
    spans = translated.sections[0].paragraphs[0].spans
    assert spans[0].text.startswith("ZH:")
    assert spans[1].text == " E = mc^2 "


def test_llm_translator_requires_config_values():
    with pytest.raises(ConfigError):
        LLMTranslator(api_key="", base_url="x", model="m")


def test_llm_translator_retries(monkeypatch):
    class DummyOpenAI:
        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr("pdf_translate.translator.OpenAI", DummyOpenAI)
    translator = LLMTranslator(api_key="k", base_url="https://x", model="m", max_attempts=3)

    calls = {"n": 0}

    def flaky(_text):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return "ok"

    monkeypatch.setattr(translator, "_request", flaky)
    assert translator.translate("hello") == "ok"
    assert calls["n"] == 2


def test_llm_translator_fails_after_retries(monkeypatch):
    class DummyOpenAI:
        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr("pdf_translate.translator.OpenAI", DummyOpenAI)
    translator = LLMTranslator(api_key="k", base_url="https://x", model="m", max_attempts=2)
    monkeypatch.setattr(translator, "_request", lambda _text: (_ for _ in ()).throw(RuntimeError("bad")))

    with pytest.raises(TranslateError):
        translator.translate("hello")


def test_translate_document_parallel_order_stable():
    doc = _doc_for_translation()

    class SlowTranslator(FakeTranslator):
        def translate(self, text: str) -> str:
            time.sleep(0.01)
            return "ZH:" + text

    translated = translate_document(doc, SlowTranslator(), max_concurrency=3)
    assert translated.sections[0].paragraphs[0].spans[0].text == "ZH:Hello world"
    assert translated.sections[0].paragraphs[1].spans[0].text == "ZH:Another paragraph"


def test_quality_retry_detects_english_heavy_translation():
    source = "This sentence should be translated into Chinese for readability."
    translated = "This sentence should be translated into Chinese for readability and clarity."
    assert _needs_quality_retry(source, translated) is True


def test_quality_retry_not_needed_when_translation_is_chinese_dominant():
    source = "This sentence should be translated into Chinese for readability."
    translated = "这句话应该被翻译成中文，以提高可读性和清晰度。"
    assert _needs_quality_retry(source, translated) is False


def test_retry_selection_prefers_lower_english_ratio():
    initial = "this remains mostly english text with several words"
    retried = "这段内容已经翻译为中文，只保留必要符号。"
    assert _is_retry_better(initial, retried) is True


def test_translate_document_preserves_sum_formula_inside_translatable_span():
    doc = DocumentModel(
        title="T",
        source_url="https://example.com",
        generated_at=None,
        sections=[
            Section(
                heading="1 Intro",
                level=1,
                paragraphs=[Paragraph(spans=[Span("Use ∑n i=1 i before the proof.", True)])],
            )
        ],
    )
    translated = translate_document(doc, FakeTranslator(lambda t: "中译:" + t), max_concurrency=1)
    out_text = translated.sections[0].paragraphs[0].spans[0].text
    assert "∑n i=1 i" in out_text
    assert out_text.startswith("中译:")


def test_translate_document_falls_back_when_placeholder_is_destroyed():
    doc = DocumentModel(
        title="T",
        source_url="https://example.com",
        generated_at=None,
        sections=[
            Section(
                heading="1 Intro",
                level=1,
                paragraphs=[Paragraph(spans=[Span("Use ∑n i=1 i before the proof.", True)])],
            )
        ],
    )

    def bad_mapper(text: str) -> str:
        return text.replace("[[MATH_0001]]", "[[BROKEN]]")

    translated = translate_document(doc, FakeTranslator(bad_mapper), max_concurrency=1)
    out_text = translated.sections[0].paragraphs[0].spans[0].text
    assert out_text == "Use ∑n i=1 i before the proof."


def test_restore_span_boundaries_keeps_leading_punctuation():
    source = ". More generally we proceed."
    translated = "更一般地我们继续"
    fixed = _restore_span_boundaries(source, translated)
    assert fixed.startswith("。")
    assert fixed.endswith("。")


def test_needs_residual_english_fix_ignores_uppercase_abbreviation():
    source = "This should be translated."
    translated = "这段内容保留 CS 70 标记。"
    assert _needs_residual_english_fix(source, translated) is False


def test_needs_residual_english_fix_detects_lowercase_english():
    source = "This should be translated."
    translated = "这段内容包含 why 这个词。"
    assert _needs_residual_english_fix(source, translated) is True
