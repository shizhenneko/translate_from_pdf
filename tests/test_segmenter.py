from __future__ import annotations

from pdf_translate.segmenter import is_math_like, segment_paragraph, segment_paragraphs


def test_is_math_like_equation_line():
    assert is_math_like("E = mc^2") is True


def test_is_math_like_plain_sentence():
    assert is_math_like("This is a normal sentence for translation.") is False


def test_segment_paragraph_splits_inline_math():
    paragraph = segment_paragraph("We compute $x^2 + y^2$ and explain results.")

    assert len(paragraph.spans) >= 2
    assert any(span.translatable is False for span in paragraph.spans)
    assert any(span.translatable is True for span in paragraph.spans)


def test_segment_paragraph_math_only_passthrough():
    paragraph = segment_paragraph("$\\alpha + \\beta = \\gamma$")

    assert len(paragraph.spans) == 1
    assert paragraph.spans[0].translatable is False


def test_segment_paragraphs_filters_empty_blocks():
    paragraphs = segment_paragraphs(["", "  ", "Hello world"])
    assert len(paragraphs) == 1
    assert paragraphs[0].spans[0].text == "Hello world"


def test_segment_paragraph_keeps_prose_translatable_with_inline_equation():
    paragraph = segment_paragraph(
        "If A = {1,2,3,4}, then the cardinality of A is 4 and we continue discussing sets."
    )

    translatable_text = "".join(span.text for span in paragraph.spans if span.translatable)
    passthrough_text = "".join(span.text for span in paragraph.spans if not span.translatable)

    assert "cardinality" in translatable_text
    assert "A = {1,2,3,4}" in passthrough_text


def test_segment_paragraph_equation_token_isolated_passthrough():
    paragraph = segment_paragraph("We compute n = k + 1 before proving the theorem.")

    assert any((not span.translatable) and ("n = k + 1" in span.text) for span in paragraph.spans)
    assert any(span.translatable and "proving the theorem" in span.text for span in paragraph.spans)


def test_segment_paragraph_keeps_non_zero_phrase_translatable():
    paragraph = segment_paragraph("The denominator must be non-zero in this definition.")
    assert any(span.translatable and "non-zero" in span.text for span in paragraph.spans)


def test_segment_paragraph_splits_formula_connector_word():
    paragraph = segment_paragraph("f(m)+f(n) as ∑n")
    assert any((not span.translatable) and "f(m)+f(n)" in span.text for span in paragraph.spans)
    assert any(span.translatable and span.text.strip().lower() == "as" for span in paragraph.spans)
    assert any((not span.translatable) and "∑n" in span.text for span in paragraph.spans)


def test_segment_paragraph_splits_long_translatable_fragment():
    text = (
        "This is the first sentence of a very long paragraph used for translation quality testing. "
        "This is the second sentence and it should be separated into another chunk when the paragraph is long enough. "
        "This is the third sentence with additional words to exceed the chunk threshold significantly."
    )
    paragraph = segment_paragraph(text)
    translatable_spans = [span for span in paragraph.spans if span.translatable]
    assert len(translatable_spans) >= 2


def test_segment_paragraph_marks_sum_product_formula_as_passthrough():
    paragraph = segment_paragraph("We write ∑n i=1 i to define the sum and continue proving bounds.")
    passthrough = [span.text for span in paragraph.spans if not span.translatable]
    translatable = [span.text for span in paragraph.spans if span.translatable]
    assert any("∑" in text and "i=1" in text for text in passthrough)
    assert any("continue proving bounds" in text for text in translatable)


def test_segment_paragraph_keeps_short_question_after_formula_translatable():
    paragraph = segment_paragraph("Note that, if |S| = k, then |P(S)| = 2k. [Why?]")
    assert any(span.translatable and "[Why?]" in span.text for span in paragraph.spans)
