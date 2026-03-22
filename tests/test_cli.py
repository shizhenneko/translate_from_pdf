from __future__ import annotations

import pytest

from pdf_translate.cli import main
from pdf_translate.types import PipelineResult


def test_cli_help_runs(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "run" in captured.out


def test_cli_run_with_fake_translator(monkeypatch, tmp_path, capsys):
    output_file = tmp_path / "x.zh.md"

    def fake_run_pipeline(url, settings, output_path=None, max_pages=None, translator=None):
        output_file.write_text("# 输出\n", encoding="utf-8")
        return PipelineResult(
            downloaded_pdf=tmp_path / "downloaded.pdf",
            output_markdown=output_path or output_file,
            page_count=2,
            section_count=2,
        )

    monkeypatch.setattr("pdf_translate.cli.run_pipeline", fake_run_pipeline)
    main(
        [
            "run",
            "--url",
            "https://example.com/doc.pdf",
            "--out",
            str(output_file),
            "--use-fake-translator",
        ]
    )
    captured = capsys.readouterr()
    assert "Output Markdown:" in captured.out


def test_cli_translate_markdown_with_fake_translator(monkeypatch, tmp_path, capsys):
    input_markdown = tmp_path / "note.md"
    output_markdown = tmp_path / "note.zh.md"
    input_markdown.write_text("# Intro\n\nHello\n", encoding="utf-8")

    def fake_translate_markdown(markdown_path, settings, output_path=None, translator=None):
        (output_path or output_markdown).write_text("# 介绍\n\n你好\n", encoding="utf-8")
        return output_path or output_markdown

    monkeypatch.setattr("pdf_translate.cli.run_markdown_translation", fake_translate_markdown)

    main(
        [
            "translate-md",
            "--in",
            str(input_markdown),
            "--out",
            str(output_markdown),
            "--use-fake-translator",
        ]
    )

    captured = capsys.readouterr()
    assert "Output Markdown:" in captured.out


def test_cli_serve_help_runs(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["serve", "--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "--port" in captured.out
