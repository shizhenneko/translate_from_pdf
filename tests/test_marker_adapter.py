from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from pdf_translate.errors import MarkerError
from pdf_translate.marker_adapter import _run_with_live_output, resolve_marker_command, run_marker


def test_run_marker_collects_markdown_and_images(monkeypatch, tmp_path, sample_pdf_path):
    output_dir = tmp_path / "marker-out"

    def fake_live_run(cmd):
        assert Path(cmd[0]).name in {"marker_single", "marker_single.exe"}
        assert "--output_dir" in cmd
        rendered_dir = output_dir / "sample"
        images_dir = rendered_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        (rendered_dir / "sample.md").write_text(
            "# Title\n\nHello.\n\n![Figure](images/figure.png)\n",
            encoding="utf-8",
        )
        (images_dir / "figure.png").write_bytes(b"png")

    monkeypatch.setattr("pdf_translate.marker_adapter._run_with_live_output", fake_live_run)

    result = run_marker(sample_pdf_path, output_dir=output_dir)

    assert result.markdown_path.name == "sample.md"
    assert len(result.image_paths) == 1
    assert result.image_paths[0].name == "figure.png"


def test_run_marker_wraps_command_failure(monkeypatch, tmp_path, sample_pdf_path):
    def bad_run(cmd):
        raise subprocess.CalledProcessError(returncode=2, cmd=cmd, output="marker failed")

    monkeypatch.setattr("pdf_translate.marker_adapter._run_with_live_output", bad_run)

    with pytest.raises(MarkerError) as exc:
        run_marker(sample_pdf_path, output_dir=tmp_path / "marker-out")

    assert "marker failed" in str(exc.value)


def test_run_marker_requires_markdown_output(monkeypatch, tmp_path, sample_pdf_path):
    def fake_run(cmd):
        output_dir = tmp_path / "marker-out"
        output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("pdf_translate.marker_adapter._run_with_live_output", fake_run)

    with pytest.raises(MarkerError):
        run_marker(sample_pdf_path, output_dir=tmp_path / "marker-out")


def test_resolve_marker_command_finds_local_windows_exe(monkeypatch, tmp_path):
    fake_python = tmp_path / "venv" / "Scripts" / "python.exe"
    fake_python.parent.mkdir(parents=True, exist_ok=True)
    fake_python.write_bytes(b"")
    fake_marker = fake_python.parent / "marker_single.exe"
    fake_marker.write_bytes(b"")

    monkeypatch.setattr("pdf_translate.marker_adapter.sys.executable", str(fake_python))
    monkeypatch.setattr("pdf_translate.marker_adapter.shutil.which", lambda _cmd: None)
    monkeypatch.setattr(
        "pdf_translate.marker_adapter._marker_command_candidates",
        lambda _cmd: [fake_python.parent / "marker_single", fake_marker],
    )

    resolved = resolve_marker_command("marker_single")

    assert Path(resolved) == fake_marker


def test_run_with_live_output_streams_and_succeeds(monkeypatch, capsys):
    class FakeStdout:
        def __init__(self, text):
            self._chars = list(text)

        def read(self, size=1):
            if not self._chars:
                return ""
            return self._chars.pop(0)

        def close(self):
            return None

    class FakeProcess:
        def __init__(self):
            self.stdout = FakeStdout("model A 10%\rmodel A 100%\nmodel B 100%\n")

        def wait(self):
            return 0

    monkeypatch.setattr("pdf_translate.marker_adapter.subprocess.Popen", lambda *args, **kwargs: FakeProcess())

    _run_with_live_output(["marker_single", "sample.pdf"])

    captured = capsys.readouterr()
    assert "model A 100%" in captured.out
    assert "model B 100%" in captured.out


def test_run_with_live_output_includes_tail_on_failure(monkeypatch):
    class FakeStdout:
        def __init__(self, text):
            self._chars = list(text)

        def read(self, size=1):
            if not self._chars:
                return ""
            return self._chars.pop(0)

        def close(self):
            return None

    class FakeProcess:
        def __init__(self):
            self.stdout = FakeStdout("downloading model\nfailed badly\n")

        def wait(self):
            return 7

    monkeypatch.setattr("pdf_translate.marker_adapter.subprocess.Popen", lambda *args, **kwargs: FakeProcess())

    with pytest.raises(subprocess.CalledProcessError) as exc:
        _run_with_live_output(["marker_single", "sample.pdf"])

    assert exc.value.returncode == 7
    assert "failed badly" in (exc.value.output or "")
