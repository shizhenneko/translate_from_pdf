from __future__ import annotations

from pdf_translate.math_preserve import (
    find_math_spans,
    has_sum_or_product,
    protect_math_fragments,
    restore_math_fragments,
    stabilize_math_layout,
)


def test_protect_and_restore_sum_product_expression():
    text = "We write ∑n i=1 i and also use ∏n i=m f(i)."
    protected, fragments = protect_math_fragments(text)
    assert "[[MATH_0001]]" in protected
    assert "[[MATH_0002]]" in protected
    restored, missing, extras = restore_math_fragments(protected, fragments)
    assert restored == text
    assert missing == []
    assert extras == []


def test_find_math_spans_detects_set_builder_notation():
    text = "Q = {a b | a,b ∈Z, b ≠ 0} is the rational set."
    spans = find_math_spans(text)
    assert any("{" in span.text and "|" in span.text for span in spans)


def test_find_math_spans_skips_prose_heavy_set_builder():
    text = "Q can be written as {a b | a,b are integers, b ≠ 0}."
    spans = find_math_spans(text)
    assert all(span.kind != "set_builder" for span in spans)


def test_stabilize_math_layout_uses_non_breaking_space_for_sum_product():
    text = "formula: ∑n i=1 i."
    stabilized = stabilize_math_layout(text)
    assert has_sum_or_product(stabilized) is True
    assert "\u00a0" in stabilized


def test_stabilize_math_layout_repairs_sum_product_and_powers():
    text = "Thus ∑n i=5 i2 = 52 +62 +···+n2."
    stabilized = stabilize_math_layout(text)
    assert "∑_{i=5}^{n}" in stabilized
    assert "i^2" in stabilized
    assert "5^2" in stabilized
    assert "6^2" in stabilized
    assert "n^2" in stabilized


def test_stabilize_math_layout_repairs_set_builder_fraction():
    text = "Q = {a b | a,b are integers, b ≠ 0}"
    stabilized = stabilize_math_layout(text)
    assert "{a/b |" in stabilized


def test_stabilize_math_layout_repairs_inline_square_powers_in_math_context():
    text = "(∀n ∈N)(n2 + n + 41 is prime) and (∃x ∈Z)(x2 = 4)."
    stabilized = stabilize_math_layout(text)
    assert "n^2 + n + 41" in stabilized
    assert "x^2 = 4" in stabilized


def test_restore_math_fragments_reports_missing_placeholder():
    text = "Use ∑n i=1 i."
    protected, fragments = protect_math_fragments(text)
    broken = protected.replace("[[MATH_0001]]", "MISSING")
    restored, missing, extras = restore_math_fragments(broken, fragments)
    assert "MISSING" in restored
    assert missing == ["[[MATH_0001]]"]
    assert extras == []
