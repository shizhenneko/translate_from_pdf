# translate_from_pdf

<div align="center">

<h3>Production-oriented PDF translation workflow for Chinese Markdown output.</h3>

<p>
  Upload a local PDF or submit a remote PDF URL, extract structured Markdown, preserve formulas as much as possible, and translate the content through a configurable LLM backend.
</p>

<p>
  <a href="https://github.com/shizhenneko/translate_from_pdf/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-1f6b4f.svg" alt="License: MIT"></a>
  <a href="https://github.com/shizhenneko/translate_from_pdf"><img src="https://img.shields.io/badge/python-3.8%2B-2b7a78.svg" alt="Python 3.8+"></a>
  <a href="https://github.com/shizhenneko/translate_from_pdf"><img src="https://img.shields.io/badge/platform-WSL%20%7C%20Windows-3a506b.svg" alt="Platform"></a>
  <a href="https://github.com/shizhenneko/translate_from_pdf"><img src="https://img.shields.io/badge/output-Markdown-4c956c.svg" alt="Output Markdown"></a>
  <a href="https://github.com/shizhenneko/translate_from_pdf"><img src="https://img.shields.io/badge/LLM-configurable-355070.svg" alt="LLM configurable"></a>
</p>

<p>
  <a href="#quick-start">Quick Start</a>
  ·
  <a href="#key-features">Key Features</a>
  ·
  <a href="#usage">Usage</a>
  ·
  <a href="#configuration">Configuration</a>
  ·
  <a href="#development">Development</a>
</p>

</div>

---

## Introduction

`translate_from_pdf` is a lightweight but practical PDF translation project for Chinese-first workflows.

Instead of treating PDF translation as a plain text conversion problem, it tries to keep the output usable:

- keep Markdown structure whenever possible
- preserve formulas, symbols, and math-like fragments
- support both local file upload and remote PDF URL input
- provide CLI and local Web UI entry points
- isolate local runtime artifacts from Git by default

Current pipeline:

```text
PDF / URL
  -> Marker extracts Markdown
  -> segmentation and math protection
  -> configurable LLM translation
  -> Chinese Markdown output
```

## Key Features

| Feature | Description |
| --- | --- |
| Local PDF workflow | Upload or process a local PDF directly |
| Remote URL workflow | Submit a public PDF URL and let the pipeline download it |
| Markdown-first output | Produce Chinese Markdown for further editing and publishing |
| Formula preservation | Protect math placeholders and symbol-heavy spans before translation |
| Configurable LLM backend | Use `LLM_*` environment variables instead of provider-branded config |
| Local Web UI | Good for demos, non-CLI users, and quick checks |
| Offline testing mode | Run with a fake translator for regression tests and local debugging |
| Windows / WSL launchers | Start quickly from common local environments |

## Repository Structure

```text
.
├─ pdf_translate/           # core package: CLI, Web, pipeline, adapters, translators
├─ tests/                   # pytest suite
├─ docs/configuration.md    # configuration reference
├─ pdf-url-to-zh-pdf.md     # planning / spec document
├─ .env.example             # env template
├─ start_wsl.sh             # one-click startup for WSL
├─ start_windows.ps1        # one-click startup for PowerShell
├─ start_windows.bat        # one-click startup for CMD
└─ README.md
```

Ignored by default through `.gitignore`:

- `.env`
- virtual environments such as `.venv`, `.venv-windows`
- `.cache/`
- `.jobs/`
- generated outputs under `pdfs/`
- local PDF and translated Markdown artifacts in the repository root

## Quick Start

### Clone the repository

```bash
git clone https://github.com/shizhenneko/translate_from_pdf.git
cd translate_from_pdf
```

### Create a virtual environment

macOS / Linux / WSL:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Install dependencies

```bash
python -m pip install -U pip
python -m pip install -e .[dev]
```

For the full PDF extraction path, install `marker-pdf` as well:

```bash
python -m pip install marker-pdf
```

### Configure environment variables

```bash
cp .env.example .env
```

Minimum required configuration for real online translation:

```dotenv
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

### Start the local Web UI

```bash
python -m pdf_translate serve
```

Then open:

```text
http://127.0.0.1:10001/
```

## Usage

### CLI

Translate a local PDF into Chinese Markdown:

```bash
python -m pdf_translate run --in /path/to/file.pdf
```

Specify an explicit output path:

```bash
python -m pdf_translate run --in /path/to/file.pdf --out output/result.zh.md
```

Translate a local Markdown file:

```bash
python -m pdf_translate translate-md --in docs/source.md --out output/source.zh.md
```

Process a remote PDF URL:

```bash
python -m pdf_translate run --url https://example.com/file.pdf
```

Run in offline fake-translator mode:

```bash
python -m pdf_translate run --in /path/to/file.pdf --use-fake-translator
python -m pdf_translate translate-md --in docs/source.md --use-fake-translator
```

### Web UI

The local Web UI supports:

- uploading a single PDF
- submitting a remote PDF URL
- polling async job status
- downloading the translated Markdown output

API endpoints:

- `POST /api/jobs/pdf`
- `POST /api/jobs/url`
- `GET /api/jobs/<job_id>`
- `GET /api/jobs/<job_id>/download/md`

## Configuration

Detailed configuration reference: [docs/configuration.md](docs/configuration.md)

Common variables:

```dotenv
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

PDF_TRANSLATE_CACHE_DIR=.cache/pdf_translate
PDF_TRANSLATE_JOBS_DIR=.jobs/pdf_translate
PDF_TRANSLATE_MARKER_COMMAND=marker_single
PDF_TRANSLATE_MARKER_OUTPUT_FORMAT=markdown
PDF_TRANSLATE_MARKER_FORCE_OCR=false
PDF_TRANSLATE_OCR_TEXT_THRESHOLD=50
PDF_TRANSLATE_OCR_LANG=eng
PDF_TRANSLATE_MAX_CONCURRENCY=2
PDF_TRANSLATE_RETRY_MAX_ATTEMPTS=3
PDF_TRANSLATE_WEB_HOST=127.0.0.1
PDF_TRANSLATE_WEB_PORT=10001
PDF_TRANSLATE_MAX_UPLOAD_MB=30
PDF_TRANSLATE_MARKDOWN_CHUNK_CHARS=4000
PDF_TRANSLATE_SYMBOL_FIX_MODE=conservative
```

Notes:

- `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` are required for real online translation
- current implementation uses the `openai` Python SDK to talk to OpenAI-compatible endpoints
- configuration names are provider-neutral and no longer tied to `OPENAI_*`
- `.env` is ignored by Git

## System Requirements

### WSL / Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils fonts-wqy-zenhei
```

### Windows

- Python `3.10+`
- working virtual environment support
- `marker-pdf` and its dependencies if you want the full extraction path

## One-Click Startup

### WSL

```bash
bash ./start_wsl.sh
```

Custom port:

```bash
bash ./start_wsl.sh 10002
```

### Windows PowerShell

```powershell
.\start_windows.ps1
```

Custom port:

```powershell
.\start_windows.ps1 -Port 10002
```

### Windows CMD

```bat
start_windows.bat
```

Notes:

- `start_wsl.sh` uses `.venv`
- `start_windows.ps1` and `start_windows.bat` use `.venv-windows`
- WSL and Windows environments are intentionally kept separate

## Output Layout

```text
pdfs/
  <input-name>.md
  assets/

.jobs/pdf_translate/<job_id>/
  manifest.json
  source/
    input.pdf
  intermediate/
    source.md
```

## Development

Run the default offline test suite:

```bash
pytest -q -m "not e2e_live"
```

Check the CLI entry:

```bash
python -m pdf_translate --help
```

Inspect the first 60 lines of generated output:

```bash
head -n 60 <output>.zh.md
```

Development expectations:

- use `pytest`
- mock external LLM/API calls in tests
- add regression coverage for pipeline-stage changes
- do not commit generated artifacts

## Design Notes

- `Marker` is the current primary extraction path
- formulas, variables, and symbol-heavy fragments should be preserved whenever possible
- tables, code blocks, and links should remain meaningful Markdown structures
- the Web UI stays intentionally lightweight while the pipeline logic remains in Python

## Roadmap

- finer-grained task progress visibility
- batch processing for multiple PDFs
- bilingual output mode
- more stable OCR fallback behavior for scanned PDFs
- richer history and preview capabilities

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
