from __future__ import annotations

from pdf_translate.markdown_translate import chunk_markdown, translate_markdown
from pdf_translate.translator import FakeTranslator


def test_chunk_markdown_keeps_fenced_code_intact():
    markdown = """# Intro

Hello world.

```python
print("hi")
print("bye")
```

## Next

Another paragraph that should be split into a separate chunk.
"""

    chunks = chunk_markdown(markdown, max_chars=50)

    assert len(chunks) >= 2
    assert any(chunk.text.startswith("## Next") for chunk in chunks)
    assert all(chunk.text.count("```") % 2 == 0 for chunk in chunks if "```" in chunk.text)


def test_translate_markdown_preserves_urls_code_and_math():
    markdown = """# Intro

Hello world.

Visit https://example.com/docs?a=1 for more details.

Inline `sum(i)` stays.

$$E = mc^2$$

```python
print("Hello")
```
"""

    translator = FakeTranslator(
        lambda text: text.replace("Hello world.", "你好世界。").replace("Visit ", "访问 ")
    )

    translated = translate_markdown(markdown, translator=translator, max_chunk_chars=80)

    assert "你好世界" in translated
    assert "https://example.com/docs?a=1" in translated
    assert "`sum(i)`" in translated
    assert "$$E = mc^2$$" in translated
    assert 'print("Hello")' in translated
