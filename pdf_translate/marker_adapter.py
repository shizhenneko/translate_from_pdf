"""Marker CLI adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import List

from .errors import MarkerError

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


@dataclass
class MarkerResult:
    markdown_path: Path
    image_paths: List[Path] = field(default_factory=list)


def _find_markdown_path(output_dir: Path) -> Path:
    matches = sorted(output_dir.rglob("*.md"))
    if not matches:
        raise MarkerError("Marker did not produce a markdown file in %s" % output_dir)
    return matches[0]


def _find_image_paths(markdown_path: Path) -> List[Path]:
    return sorted(
        path
        for path in markdown_path.parent.rglob("*")
        if path.is_file() and path.suffix.lower() in _IMAGE_EXTS
    )


def _marker_command_candidates(command: str) -> List[Path]:
    candidates: List[Path] = []

    raw = Path(command)
    if raw.parent != Path():
        candidates.append(raw)

    executable_dir = Path(sys.executable).resolve().parent
    candidates.append(executable_dir / command)
    if os.name == "nt" and not command.lower().endswith(".exe"):
        candidates.append(executable_dir / (command + ".exe"))

    repo_root = Path(__file__).resolve().parents[1]
    candidates.append(repo_root / ".venv-windows" / "Scripts" / command)
    if os.name == "nt" and not command.lower().endswith(".exe"):
        candidates.append(repo_root / ".venv-windows" / "Scripts" / (command + ".exe"))

    deduped: List[Path] = []
    seen = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def resolve_marker_command(command: str) -> str:
    direct = shutil.which(command)
    if direct:
        return direct

    for candidate in _marker_command_candidates(command):
        if candidate.exists():
            return str(candidate)

    return command


def _run_with_live_output(cmd: List[str]) -> None:
    """Run Marker while streaming stdout/stderr to the current console.

    Marker may spend a long time downloading Hugging Face models on first run.
    We deliberately avoid capture_output=True here so users can see real-time
    download bars and initialization logs instead of a silent "hang".
    """

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    if process.stdout is None:
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(returncode=return_code, cmd=cmd)
        return

    tail_parts: List[str] = []
    tail_limit = 8000
    try:
        while True:
            chunk = process.stdout.read(1)
            if chunk == "":
                break
            sys.stdout.write(chunk)
            sys.stdout.flush()
            tail_parts.append(chunk)
            if sum(len(part) for part in tail_parts) > tail_limit:
                joined = "".join(tail_parts)
                tail_parts = [joined[-tail_limit:]]
    finally:
        process.stdout.close()

    return_code = process.wait()
    if return_code != 0:
        detail = "".join(tail_parts).strip()
        raise subprocess.CalledProcessError(
            returncode=return_code,
            cmd=cmd,
            output=detail,
        )


def run_marker(
    pdf_path: Path,
    output_dir: Path,
    command: str = "marker_single",
    force_ocr: bool = False,
) -> MarkerResult:
    """Convert a PDF into local markdown via Marker."""

    if not pdf_path.exists():
        raise MarkerError("Input PDF does not exist: %s" % pdf_path)

    output_dir.mkdir(parents=True, exist_ok=True)

    resolved_command = resolve_marker_command(command)

    cmd = [
        resolved_command,
        str(pdf_path),
        "--output_dir",
        str(output_dir),
        "--output_format",
        "markdown",
    ]
    if force_ocr:
        cmd.append("--force_ocr")

    try:
        _run_with_live_output(cmd)
    except FileNotFoundError as exc:
        raise MarkerError(
            "Marker command not found: %s. Install marker-pdf and ensure the command is on PATH."
            % command
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or exc.output or "").strip()
        if detail:
            raise MarkerError("Marker failed: %s" % detail) from exc
        raise MarkerError("Marker exited with code %d" % exc.returncode) from exc

    markdown_path = _find_markdown_path(output_dir)
    return MarkerResult(
        markdown_path=markdown_path,
        image_paths=_find_image_paths(markdown_path),
    )
