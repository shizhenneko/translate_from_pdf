# PDF URL -> zh-CN Reflow PDF (DeepSeek via configurable LLM adapter)

## TL;DR

> **Quick Summary**: Build a Python CLI that downloads a PDF from a URL, extracts text/images (OCR only when needed), translates the content to Simplified Chinese with DeepSeek or another compatible LLM backend (`.env` driven), and outputs a readable Chinese Markdown document.
>
> **Deliverables**:
> - A Python CLI pipeline: `python -m pdf_translate run --url <pdf-url>`
> - A translated Markdown output: `<input-name>.zh.md`
> - TDD test suite (pytest) with mocked LLM calls + fixture PDFs
> - Setup + usage docs (README)
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES (2 waves)
> **Critical Path**: extraction/structuring -> translation chunking -> Markdown output

---

## Context

### Original Request
User wants to fetch an online `.pdf` URL, extract information, translate to Chinese, and produce a Chinese Markdown document for reading.

### Interview Summary (confirmed)
- Language: **Simplified Chinese (zh-CN)**
- Translation style: **academic literal**; terminology consistency > paraphrasing
- Layout goal: **readability-first** (reflow by headings/sections; no strict original pagination)
- Math/formulas: **keep as-is** (do not translate formulas/symbol-heavy lines)
- Figures/tables: **best-effort keep & insert** into output PDF
- OCR: **auto-enable only for pages with too little extractable text**
- Output: **Chinese-only PDF** including **cover + TOC + original source URL**
- Engine: **DeepSeek v3.2** via a configurable **LLM adapter**; config via **`.env`**
- Interface: **Python CLI**
- Dependencies: user allows **system-level packages** (OCR + PDF tooling)
- Tests: **YES, TDD**
- Glossary: not required initially

Example URL:
- https://www.eecs70.org/assets/pdf/notes/n14.pdf

### Metis Review (gaps addressed by defaults/guardrails)
Metis flagged scope creep + failure modes. This plan applies explicit guardrails:
- Reflow PDF does **not** preserve original pagination/two-column placement.
- Figures are **best-effort**; placement may be approximate.
- OCR is only a fallback; no “perfect reconstruction” target.
- Live LLM calls are **mocked in tests** (no API calls during CI/test runs).

---

## Work Objectives

### Core Objective
Provide a reliable, repeatable CLI pipeline that turns an English/math-heavy PDF into a readable zh-CN PDF, while controlling cost, failures, and output quality via deterministic chunking and robust fallbacks.

### Concrete Deliverables
- `pdf_translate/` Python package implementing pipeline stages
- `tests/` pytest suite using fixture PDFs and mocked LLM responses
- `README.md` with setup, `.env` schema, examples, troubleshooting
- Output Markdown: `n14.zh.md` (derived from URL basename)

### Definition of Done
- [ ] `pytest -q` passes locally
- [ ] `python -m pdf_translate --help` exits 0
- [ ] `python -m pdf_translate run --url https://www.eecs70.org/assets/pdf/notes/n14.pdf` produces `n14.zh.md`
- [ ] `head -n 60 n14.zh.md` includes Chinese text and the source URL

### Must NOT Have (Guardrails)
- No web UI / server mode
- No multi-provider translation abstraction (DeepSeek only, behind a thin adapter)
- No promise of exact figure placement or table reconstruction
- No calls to real LLM endpoints during tests
- No “translate formulas” attempt beyond prompt constraints + heuristic passthrough

### Defaults Applied (override via flags/env)
- Translate scope: headings + body paragraphs + captions when extracted as text; exclude boilerplate headers/footers; preserve math/code spans
- OCR threshold: page `text_len < 50` triggers OCR (configurable)
- OCR language: `eng`
- Concurrency: default 1-3 concurrent translation requests (configurable)
- Safety: input treated as untrusted; ignore any instructions embedded in PDF content

---

## Verification Strategy (MANDATORY)

UNIVERSAL RULE: All verification steps are agent-executable (commands and automated checks). No manual/visual verification required.

### Test Decision
- Infrastructure exists: likely NO (repo is new)
- Automated tests: **YES (TDD)**
- Framework: **pytest** (default)

### Agent-Executed QA Scenarios (E2E smoke)

Scenario: End-to-end translate sample PDF
  Tool: Bash
  Preconditions: `.env` configured; system deps installed; venv ready
  Steps:
    1. Run: `python -m pdf_translate run --url https://www.eecs70.org/assets/pdf/notes/n14.pdf`
    2. Assert: output file `n14.zh.md` exists and size > 0
    3. Run: `head -n 80 n14.zh.md`
    4. Assert: contains Chinese characters; contains original URL
  Expected Result: A valid Chinese-readable Markdown document is produced
  Evidence: stdout/stderr logs captured by runner

Scenario: OCR fallback triggers only on low-text pages (fixture)
  Tool: pytest
  Preconditions: fixture PDFs exist (one text-based, one scanned page)
  Steps:
    1. Run: `pytest -q -k ocr_fallback`
  Expected Result: OCR invoked only when page text_len < threshold
  Evidence: pytest output

---

## Technical Approach (Implementation Notes)

### Proposed Pipeline
1) Download URL -> local PDF bytes/file
2) Extract per-page text + images
3) Infer structure for reflow (headings/sections/paragraphs; strip repeated headers/footers)
4) Segment into spans: translatable vs passthrough (math/code)
5) Translate spans in chunks with retries/backoff + optional cache
6) Write translated Markdown with localized asset links

### Library Defaults
- Download: `httpx` (redirects, timeouts) or `requests` (acceptable)
- PDF extraction + rendering page->image: `PyMuPDF` (`pymupdf` / `fitz`)
- OCR fallback: `pytesseract` + system `tesseract-ocr` (OCR language default `eng`)
- `.env` loading: `python-dotenv`
- CLI: `typer`
- Tests: `pytest`, `respx` (http mocking) optional

### System Dependencies (Ubuntu/WSL-friendly)
- OCR: `tesseract-ocr`, `tesseract-ocr-eng`
- PDF inspection: `poppler-utils` (provides `pdfinfo`, `pdftotext`)

### `.env` Contract (defaults; keep configurable)
- `LLM_API_KEY`: DeepSeek or other provider API key
- `LLM_BASE_URL`: default `https://api.deepseek.com/v1` (verify with official docs)
- `LLM_MODEL`: default to the selected model id (verify with docs)
- Optional: `PDF_TRANSLATE_MAX_CONCURRENCY`, `PDF_TRANSLATE_CACHE_DIR`, `PDF_TRANSLATE_OCR_TEXT_THRESHOLD`

Recommended additional knobs (optional, but useful for cost/resume):
- `PDF_TRANSLATE_MAX_PAGES` (or `--max-pages`) to cap runaway costs
- `PDF_TRANSLATE_ENABLE_CACHE=1` to cache translated chunks and resume on failure

### Math/Formula Preservation
Primary mechanism: prompt constraints + heuristic classification.
- Prompt: “Do NOT translate mathematical expressions/equations/symbol-heavy lines; keep them exactly unchanged.”
- Heuristic: mark a line/span as passthrough if symbol ratio is high, contains many operators, Greek letters, or resembles code.

### Figures/Tables Best-Effort
Default policy (readability-first):
- Extract page images; attach them near the most relevant section when a robust anchor exists; otherwise append to end of the nearest section with “Figure (from page N)”.
- If extraction fails, omit image with a logged warning (no hard failure).

---

## Execution Strategy

Wave 1 (Start Immediately):
- Task 1: Repo skeleton + CLI + config + test harness
- Task 2: Downloader module + tests
- Task 3: LLM adapter (DeepSeek/OpenAI SDK) + mocked tests

Wave 2 (After Wave 1):
- Task 4: PDF extraction (text/images) + tests
- Task 5: OCR fallback module + tests
- Task 6: Structure inference + segmentation (math passthrough) + tests
- Task 7: Renderer (cover/TOC/content/images) + tests
- Task 8: End-to-end command + docs + smoke verification

---

## TODOs

Note: Each TODO is designed for TDD (RED -> GREEN -> REFACTOR). All acceptance criteria are command-verifiable.

- [ ] 1. Create Python project skeleton (package + CLI) with `.env` config loading

  What to do:
  - Choose package name `pdf_translate` and CLI entry via `python -m pdf_translate`
  - Implement config loader: reads `.env`, validates required env vars, prints clear errors
  - Add structured logging (timestamps + stage names)

  Recommended Agent Profile:
  - Category: `quick`
  - Skills: (none)

  Parallelization:
  - Can Run In Parallel: YES (Wave 1)
  - Blocks: Tasks 2-8

  References:
  - Official dotenv: https://pypi.org/project/python-dotenv/
  - Typer docs: https://typer.tiangolo.com/

  Acceptance Criteria:
  - [ ] `python -m pdf_translate --help` exits 0
  - [ ] `pytest -q` passes (initial scaffold tests)

- [ ] 2. Implement robust PDF downloader (URL -> file) with retries and safe naming

  What to do:
  - Download with timeouts, redirects, and content-type sniffing
  - Derive output base name from URL path (e.g., `n14`), sanitize characters
  - Detect HTML error pages saved as `.pdf` (guardrail)

  Recommended Agent Profile:
  - Category: `quick`
  - Skills: (none)

  Parallelization:
  - Can Run In Parallel: YES (Wave 1)
  - Blocked By: Task 1

  References:
  - httpx docs: https://www.python-httpx.org/

  Acceptance Criteria:
  - [ ] `pytest -q -k download` passes
  - [ ] Downloaded file begins with `%PDF-` magic bytes for valid PDFs

- [ ] 3. Implement DeepSeek translator adapter (OpenAI SDK) + test doubles

  What to do:
  - Wrap OpenAI SDK client with base_url + model from env
  - Implement chunk translation with retry/backoff and deterministic ordering
  - Provide a “fake translator” for tests (no network)
  - Prompt template enforces academic literal style and math passthrough

  Recommended Agent Profile:
  - Category: `unspecified-high`
  - Skills: (none)

  Parallelization:
  - Can Run In Parallel: YES (Wave 1)
  - Blocked By: Task 1

  References:
  - OpenAI Python SDK: https://github.com/openai/openai-python
  - DeepSeek OpenAI-compat docs: (fill in from research; keep env-configurable)

  Acceptance Criteria:
  - [ ] `pytest -q -k translate_unit` passes
  - [ ] Tests assert: math-like spans unchanged; non-math spans translated (via fake)

- [ ] 4. Extract PDF text + images per page (PyMuPDF) with metrics

  What to do:
  - Extract per-page plain text
  - Extract images (best-effort) with page association
  - Compute metrics: `text_len`, `has_images`, etc. (used for OCR fallback)

  Recommended Agent Profile:
  - Category: `unspecified-high`
  - Skills: (none)

  Parallelization:
  - Can Run In Parallel: NO (Wave 2)
  - Blocked By: Task 2

  References:
  - PyMuPDF docs: https://pymupdf.readthedocs.io/

  Acceptance Criteria:
  - [ ] `pytest -q -k extract` passes
  - [ ] Page count from extraction matches `pdfinfo` (fixture)

- [ ] 5. OCR fallback (page-level) for low-text pages

  What to do:
  - If extracted `text_len` below threshold, render page to image and OCR
  - OCR language default: `eng`
  - Ensure OCR is NOT run on normal text pages

  Recommended Agent Profile:
  - Category: `unspecified-high`
  - Skills: (none)

  Parallelization:
  - Can Run In Parallel: YES (Wave 2)
  - Blocked By: Task 4

  References:
  - pytesseract docs: https://pypi.org/project/pytesseract/
  - tesseract docs: https://tesseract-ocr.github.io/

  Acceptance Criteria:
  - [ ] `pytest -q -k ocr_fallback` passes

- [ ] 6. Structure inference + segmentation (headings/paragraphs + math passthrough)

  What to do:
  - Strip repeated headers/footers via frequency heuristics
  - Detect headings to build section hierarchy (for TOC)
  - Split into paragraphs and spans
  - Mark spans as translatable/passthrough (math/code)

  Recommended Agent Profile:
  - Category: `ultrabrain`
  - Skills: (none)

  Parallelization:
  - Can Run In Parallel: YES (Wave 2)
  - Blocked By: Tasks 4-5

  Acceptance Criteria:
  - [ ] `pytest -q -k structure` passes
  - [ ] Fixture produces at least 3 headings and non-empty body paragraphs

- [ ] 7. Render translated content to a Chinese-readable PDF (cover + TOC + images)

  What to do:
  - Embed a CJK font (Noto Sans/Serif CJK)
  - Prefer vendored font path `assets/fonts/NotoSerifCJKsc-Regular.otf` (document download)
  - Generate cover: title (best-effort), source URL, generated timestamp
  - Generate TOC from detected headings
  - Render sections/paragraphs with basic typography (margins, line height)
  - Insert images best-effort

  Recommended Agent Profile:
  - Category: `unspecified-high`
  - Skills: (none)

  Parallelization:
  - Can Run In Parallel: YES (Wave 2)
  - Blocked By: Task 6

  Acceptance Criteria:
  - [ ] markdown output tests pass

- [ ] 8. End-to-end command (`run`) + docs + smoke verification script

  What to do:
  - Implement `run` subcommand to execute the full pipeline
  - Add `README.md` documenting:
    - system deps install commands
    - venv setup
    - `.env` schema
    - usage examples
    - troubleshooting (OCR missing, API errors)

  Recommended Agent Profile:
  - Category: `writing`
  - Skills: (none)

  Parallelization:
  - Can Run In Parallel: NO (final integration)
  - Blocked By: Tasks 1-7

  Acceptance Criteria:
  - [ ] `python -m pdf_translate run --url https://www.eecs70.org/assets/pdf/notes/n14.pdf` produces `n14.zh.md`
  - [ ] `head -n 80 n14.zh.md` includes Chinese + source URL

---

## Commit Strategy (suggested)
- Commit after Wave 1 tasks (scaffold + downloader + translator adapter)
- Commit after Wave 2 extraction/OCR/structure
- Final commit after markdown output + E2E + docs

---

## Success Criteria

Verification Commands (expected pass):
```bash
python -m pdf_translate --help
pytest -q
python -m pdf_translate run --url https://www.eecs70.org/assets/pdf/notes/n14.pdf
head -n 60 n14.zh.md
```
