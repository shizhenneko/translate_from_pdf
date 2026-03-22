from __future__ import annotations

from pdf_translate.text_normalize import count_control_chars, normalize_text


def test_normalize_text_repairs_common_math_artifacts():
    text = "if y /∈ A and b ̸= 0 then A ∩ /0 = /0"
    normalized = normalize_text(text, mode="conservative")
    assert "∉" in normalized
    assert "≠" in normalized
    assert "∅" in normalized
    assert "/∈" not in normalized
    assert "̸=" not in normalized


def test_normalize_text_does_not_replace_slash_zero_outside_math_context():
    text = "URL path /0 should remain literal."
    normalized = normalize_text(text, mode="conservative")
    assert "/0" in normalized
    assert "∅" not in normalized


def test_normalize_text_strips_control_chars():
    text = "A\x00B\x07C"
    assert count_control_chars(text) == 2
    normalized = normalize_text(text, mode="conservative")
    assert normalized == "ABC"
    assert count_control_chars(normalized) == 0


def test_normalize_text_off_mode_only_removes_controls():
    text = "x /∈ A and /0\x00"
    normalized = normalize_text(text, mode="off")
    assert normalized == "x /∈ A and /0"


def test_normalize_text_replaces_private_use_brace_fragments():
    text = "\uf8f1\n\uf8f4\n\uf8f2\n\uf8f4\n\uf8f3"
    normalized = normalize_text(text, mode="conservative")
    assert "\uf8f1" not in normalized
    assert "\uf8f2" not in normalized
    assert "\uf8f3" not in normalized
    assert "\uf8f4" not in normalized
    assert "{" in normalized
    assert "}" in normalized
    assert "|" in normalized
