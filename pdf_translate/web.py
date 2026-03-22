"""Flask web entrypoints for single-PDF translation jobs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
import re
from threading import Lock
import uuid
from typing import Callable, Dict, Optional

from flask import Flask, jsonify, render_template_string, request, send_file

from .config import Settings
from .downloader import download_pdf
from .errors import JobError, PDFTranslateError, exit_code_for
from .pipeline import run_file_pipeline
from .translator import BaseTranslator
from .types import PipelineResult

_INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>translate_from_pdf</title>
  <style>
    :root {
      --bg: #f3f5ef;
      --panel: rgba(255, 255, 255, 0.88);
      --panel-strong: #ffffff;
      --line: rgba(25, 49, 37, 0.12);
      --text: #18231d;
      --muted: #5d6c63;
      --primary: #1f6b4f;
      --primary-strong: #124734;
      --accent: #dceee3;
      --success: #146c43;
      --danger: #9f2d2d;
      --shadow: 0 18px 50px rgba(19, 39, 31, 0.10);
      --radius-xl: 28px;
      --radius-lg: 18px;
      --radius-md: 14px;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(108, 162, 126, 0.18), transparent 26rem),
        radial-gradient(circle at right 15%, rgba(215, 232, 195, 0.45), transparent 24rem),
        linear-gradient(180deg, #f8faf6 0%, var(--bg) 100%);
    }

    .shell {
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      padding: 40px 0 56px;
    }

    .hero {
      display: grid;
      grid-template-columns: 1.3fr 0.9fr;
      gap: 20px;
      align-items: stretch;
      margin-bottom: 20px;
    }

    .hero-card,
    .panel {
      background: var(--panel);
      backdrop-filter: blur(10px);
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
    }

    .hero-card {
      padding: 28px;
    }

    .hero h1 {
      margin: 0 0 12px;
      font-size: clamp(2rem, 4vw, 3.25rem);
      line-height: 1.05;
      letter-spacing: -0.04em;
    }

    .hero p {
      margin: 0;
      color: var(--muted);
      font-size: 1.02rem;
      line-height: 1.8;
      max-width: 58ch;
    }

    .hero-points {
      display: grid;
      gap: 10px;
      padding: 24px;
    }

    .hero-points strong {
      display: block;
      margin-bottom: 4px;
      font-size: 0.95rem;
    }

    .hero-points span {
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.6;
    }

    .point {
      padding: 14px 16px;
      border-radius: var(--radius-lg);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.90), rgba(235, 244, 238, 0.85));
      border: 1px solid rgba(31, 107, 79, 0.10);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 20px;
      align-items: start;
    }

    .panel {
      padding: 24px;
    }

    .panel h2 {
      margin: 0 0 10px;
      font-size: 1.2rem;
    }

    .panel > p {
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.7;
    }

    .dropzone {
      display: block;
      border: 1.5px dashed rgba(31, 107, 79, 0.28);
      background: linear-gradient(180deg, rgba(236, 245, 239, 0.78), rgba(255, 255, 255, 0.92));
      border-radius: 22px;
      padding: 22px;
      cursor: pointer;
      transition: transform 140ms ease, border-color 140ms ease, background 140ms ease;
    }

    .dropzone:hover,
    .dropzone.is-active {
      transform: translateY(-1px);
      border-color: rgba(31, 107, 79, 0.48);
      background: linear-gradient(180deg, rgba(226, 241, 232, 0.95), rgba(255, 255, 255, 0.98));
    }

    .dropzone input {
      display: none;
    }

    .dropzone-title {
      display: block;
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 8px;
    }

    .dropzone-subtitle {
      display: block;
      color: var(--muted);
      line-height: 1.7;
      font-size: 0.95rem;
    }

    .selected-file {
      margin: 14px 0 0;
      font-size: 0.92rem;
      color: var(--primary-strong);
      min-height: 1.4em;
    }

    .field {
      width: 100%;
      border: 1px solid rgba(24, 35, 29, 0.12);
      background: rgba(255, 255, 255, 0.95);
      border-radius: 14px;
      padding: 14px 16px;
      color: var(--text);
      font-size: 0.96rem;
      outline: none;
      transition: border-color 140ms ease, box-shadow 140ms ease;
    }

    .field:focus {
      border-color: rgba(31, 107, 79, 0.55);
      box-shadow: 0 0 0 4px rgba(31, 107, 79, 0.10);
    }

    .actions {
      display: flex;
      gap: 12px;
      margin-top: 18px;
      flex-wrap: wrap;
    }

    .button,
    button {
      appearance: none;
      border: 0;
      border-radius: 999px;
      padding: 12px 18px;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
      transition: transform 140ms ease, opacity 140ms ease, background 140ms ease;
    }

    .button-primary {
      background: linear-gradient(135deg, var(--primary) 0%, #2b8c67 100%);
      color: #fff;
    }

    .button-secondary {
      background: rgba(31, 107, 79, 0.08);
      color: var(--primary-strong);
    }

    .button:hover,
    button:hover {
      transform: translateY(-1px);
    }

    .button:disabled,
    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
      transform: none;
    }

    .status-panel {
      margin-top: 20px;
      display: grid;
      gap: 16px;
    }

    .status-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(24, 35, 29, 0.06);
      color: var(--text);
      font-size: 0.9rem;
      font-weight: 700;
    }

    .badge::before {
      content: "";
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: #9ca3af;
    }

    .badge.status-queued::before,
    .badge.status-running::before {
      background: #c4841d;
    }

    .badge.status-succeeded::before {
      background: var(--success);
    }

    .badge.status-failed::before {
      background: var(--danger);
    }

    .meta {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }

    .meta-card {
      padding: 14px 16px;
      border-radius: var(--radius-lg);
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid rgba(24, 35, 29, 0.08);
    }

    .meta-card small {
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .meta-card strong {
      display: block;
      word-break: break-word;
      line-height: 1.5;
      font-size: 0.96rem;
    }

    pre {
      margin: 0;
      background: #122019;
      color: #e8f3ec;
      padding: 18px;
      border-radius: 20px;
      overflow: auto;
      line-height: 1.6;
      font-size: 0.9rem;
      border: 1px solid rgba(255, 255, 255, 0.06);
      min-height: 220px;
    }

    .links {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    .links a {
      display: inline-flex;
      align-items: center;
      text-decoration: none;
    }

    .hint {
      margin-top: 14px;
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.7;
    }

    @media (max-width: 860px) {
      .hero,
      .grid {
        grid-template-columns: 1fr;
      }

      .meta {
        grid-template-columns: 1fr;
      }

      .shell {
        width: min(100% - 20px, 1120px);
        padding-top: 20px;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-card">
        <h1>translate_from_pdf</h1>
        <p>一个简洁的本地 PDF 翻译工作台。你可以上传单个 PDF，或者直接输入 PDF 链接，由系统下载、提取 Markdown、翻译为中文并生成可下载结果。</p>
      </div>
      <div class="hero-card hero-points">
        <div class="point">
          <strong>Markdown 优先</strong>
          <span>保留结构，方便二次编辑、发布和纳入知识库。</span>
        </div>
        <div class="point">
          <strong>异步任务</strong>
          <span>提交后自动轮询，不需要手动刷新状态。</span>
        </div>
        <div class="point">
          <strong>本地优先</strong>
          <span>适合在 WSL 或 Windows 本机快速启动和调试。</span>
        </div>
      </div>
    </section>

    <section class="grid">
      <form id="upload-form" class="panel">
        <h2>上传 PDF</h2>
        <p>适合本地文件。页面会将文件提交为异步任务，并持续查询状态直到完成。</p>
        <label id="dropzone" class="dropzone">
          <input id="pdf-file" type="file" name="file" accept=".pdf,application/pdf" required>
          <span class="dropzone-title">点击选择 PDF，或将文件拖到这里</span>
          <span class="dropzone-subtitle">支持单个 PDF 文件。建议上传结构清晰、扫描质量较高的文档，以获得更稳定的 Markdown 输出。</span>
        </label>
        <div id="selected-file" class="selected-file">尚未选择文件</div>
        <div class="actions">
          <button id="upload-submit" type="submit" class="button button-primary">开始处理文件</button>
        </div>
      </form>

      <form id="url-form" class="panel">
        <h2>使用 PDF URL</h2>
        <p>适合论文直链或公开资源。系统会先下载 PDF，再走与上传模式一致的解析与翻译流程。</p>
        <input id="pdf-url" class="field" type="url" name="url" placeholder="https://example.com/file.pdf" required>
        <div class="actions">
          <button id="url-submit" type="submit" class="button button-primary">下载并处理</button>
          <button id="clear-output" type="button" class="button button-secondary">清空状态</button>
        </div>
        <div class="hint">仅接受以 `http://` 或 `https://` 开头，且指向 PDF 资源的链接。</div>
      </form>
    </section>

    <section class="panel status-panel">
      <div class="status-head">
        <div>
          <h2>任务状态</h2>
          <p>这里会展示任务状态、阶段、任务编号以及原始返回结果。</p>
        </div>
        <span id="status-badge" class="badge">等待提交</span>
      </div>

      <div class="meta">
        <div class="meta-card">
          <small>Job ID</small>
          <strong id="job-id">-</strong>
        </div>
        <div class="meta-card">
          <small>Stage</small>
          <strong id="job-stage">idle</strong>
        </div>
        <div class="meta-card">
          <small>Result</small>
          <strong id="job-result">尚未开始</strong>
        </div>
      </div>

      <div id="links" class="links"></div>
      <pre id="status">{
  "status": "idle",
  "message": "等待上传或输入 URL"
}</pre>
    </section>
  </div>
  <script>
    const uploadForm = document.getElementById("upload-form");
    const urlForm = document.getElementById("url-form");
    const statusNode = document.getElementById("status");
    const linksNode = document.getElementById("links");
    const statusBadge = document.getElementById("status-badge");
    const jobIdNode = document.getElementById("job-id");
    const stageNode = document.getElementById("job-stage");
    const resultNode = document.getElementById("job-result");
    const fileInput = document.getElementById("pdf-file");
    const selectedFileNode = document.getElementById("selected-file");
    const dropzone = document.getElementById("dropzone");
    const uploadSubmit = document.getElementById("upload-submit");
    const urlSubmit = document.getElementById("url-submit");
    const clearOutput = document.getElementById("clear-output");

    function setBusy(busy) {
      uploadSubmit.disabled = busy;
      urlSubmit.disabled = busy;
      uploadSubmit.textContent = busy ? "处理中..." : "开始处理文件";
      urlSubmit.textContent = busy ? "处理中..." : "下载并处理";
    }

    function setStatusBadge(status) {
      const normalized = status || "idle";
      statusBadge.className = `badge status-${normalized}`;
      statusBadge.textContent = {
        idle: "等待提交",
        queued: "任务排队中",
        running: "任务执行中",
        succeeded: "任务已完成",
        failed: "任务失败",
      }[normalized] || normalized;
    }

    function renderStatus(data) {
      const status = data.status || "idle";
      setStatusBadge(status);
      jobIdNode.textContent = data.job_id || "-";
      stageNode.textContent = data.stage || "-";
      resultNode.textContent = data.error ? "执行失败" : (
        status === "succeeded" ? "可下载" :
        status === "running" ? "处理中" :
        status === "queued" ? "等待执行" : "尚未开始"
      );
      statusNode.textContent = JSON.stringify(data, null, 2);
    }

    function resetOutput() {
      linksNode.innerHTML = "";
      renderStatus({
        status: "idle",
        stage: "idle",
        message: "等待上传或输入 URL",
      });
    }

    function updateSelectedFile() {
      const file = fileInput.files && fileInput.files[0];
      selectedFileNode.textContent = file
        ? `已选择：${file.name} (${Math.max(1, Math.round(file.size / 1024))} KB)`
        : "尚未选择文件";
    }

    async function poll(jobId) {
      while (true) {
        const res = await fetch(`/api/jobs/${jobId}`);
        const data = await res.json();
        renderStatus(data);
        if (data.status === "succeeded") {
          linksNode.innerHTML = `
            <a class="button button-primary" href="/api/jobs/${jobId}/download/md">下载中文 Markdown</a>
          `;
          setBusy(false);
          return;
        }
        if (data.status === "failed") {
          setBusy(false);
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
    }

    uploadForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!fileInput.files || !fileInput.files[0]) {
        resetOutput();
        renderStatus({ status: "failed", stage: "validation", error: "请先选择 PDF 文件" });
        return;
      }
      linksNode.innerHTML = "";
      setBusy(true);
      const payload = new FormData(uploadForm);
      const res = await fetch("/api/jobs/pdf", { method: "POST", body: payload });
      const data = await res.json();
      renderStatus(data);
      if (res.ok && data.job_id) {
        poll(data.job_id);
        return;
      }
      setBusy(false);
    });

    urlForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      linksNode.innerHTML = "";
      setBusy(true);
      const url = document.getElementById("pdf-url").value.trim();
      const res = await fetch("/api/jobs/url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      renderStatus(data);
      if (res.ok && data.job_id) {
        poll(data.job_id);
        return;
      }
      setBusy(false);
    });

    fileInput.addEventListener("change", updateSelectedFile);
    clearOutput.addEventListener("click", resetOutput);

    ["dragenter", "dragover"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropzone.classList.add("is-active");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropzone.classList.remove("is-active");
      });
    });

    dropzone.addEventListener("drop", (event) => {
      const files = event.dataTransfer && event.dataTransfer.files;
      if (!files || !files.length) {
        return;
      }
      fileInput.files = files;
      updateSelectedFile();
    });

    resetOutput();
  </script>
</body>
</html>
"""


def _sanitize_filename(name: str) -> str:
    base = Path(name or "input.pdf").name
    return re.sub(r"[^A-Za-z0-9._-]+", "-", base) or "input.pdf"


def _manifest_path(job_dir: Path) -> Path:
    return job_dir / "manifest.json"


def _read_manifest(job_dir: Path) -> Dict[str, object]:
    path = _manifest_path(job_dir)
    if not path.exists():
        raise JobError("Job manifest not found for %s" % job_dir.name)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(job_dir: Path, payload: Dict[str, object]) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    path = _manifest_path(job_dir)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


class JobManager:
    def __init__(
        self,
        *,
        settings: Settings,
        pipeline_runner: Callable[..., PipelineResult],
        url_pipeline_runner: Optional[Callable[..., PipelineResult]] = None,
        translator: Optional[BaseTranslator] = None,
        max_workers: int = 1,
    ) -> None:
        self.settings = settings
        self.pipeline_runner = pipeline_runner
        self.url_pipeline_runner = url_pipeline_runner or self._default_url_pipeline_runner
        self.translator = translator
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: Dict[str, Path] = {}
        self._lock = Lock()

    def submit_pdf(self, filename: str, data: bytes) -> str:
        job_id = uuid.uuid4().hex[:12]
        job_dir = self.settings.jobs_dir / job_id
        source_dir = job_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        input_pdf = source_dir / _sanitize_filename(filename)
        input_pdf.write_bytes(data)

        payload = {
            "job_id": job_id,
            "status": "queued",
            "stage": "queued",
            "error": None,
            "input_pdf": str(input_pdf),
            "marker_markdown": None,
            "translated_markdown": None,
            "output_markdown": None,
            "submitted_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
        _write_manifest(job_dir, payload)
        with self._lock:
            self._jobs[job_id] = job_dir
        self.executor.submit(self._run_file_job, job_id, input_pdf, job_dir)
        return job_id

    def submit_url(self, url: str) -> str:
        job_id = uuid.uuid4().hex[:12]
        job_dir = self.settings.jobs_dir / job_id
        payload = {
            "job_id": job_id,
            "status": "queued",
            "stage": "queued",
            "error": None,
            "input_pdf": None,
            "source_url": url,
            "marker_markdown": None,
            "translated_markdown": None,
            "output_markdown": None,
            "submitted_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
        _write_manifest(job_dir, payload)
        with self._lock:
            self._jobs[job_id] = job_dir
        self.executor.submit(self._run_url_job, job_id, url, job_dir)
        return job_id

    def _run_file_job(self, job_id: str, input_pdf: Path, job_dir: Path) -> None:
        payload = _read_manifest(job_dir)
        payload["status"] = "running"
        payload["stage"] = "starting"
        _write_manifest(job_dir, payload)
        try:
            result = self.pipeline_runner(
                input_pdf,
                settings=self.settings,
                job_dir=job_dir,
                translator=self.translator,
            )
            payload.update(
                {
                    "status": "succeeded",
                    "stage": result.stage or "done",
                    "error": None,
                    "input_pdf": str(result.input_pdf or input_pdf),
                    "marker_markdown": str(result.marker_markdown) if result.marker_markdown else None,
                    "translated_markdown": (
                        str(result.translated_markdown) if result.translated_markdown else None
                    ),
                    "output_markdown": str(result.output_markdown),
                }
            )
            _write_manifest(job_dir, payload)
        except Exception as exc:
            payload.update(
                {
                    "status": "failed",
                    "stage": payload.get("stage") or "failed",
                    "error": str(exc),
                }
            )
            _write_manifest(job_dir, payload)

    def _run_url_job(self, job_id: str, url: str, job_dir: Path) -> None:
        payload = _read_manifest(job_dir)
        payload["status"] = "running"
        payload["stage"] = "downloading"
        _write_manifest(job_dir, payload)
        try:
            result = self.url_pipeline_runner(
                url,
                settings=self.settings,
                job_dir=job_dir,
                translator=self.translator,
            )
            payload.update(
                {
                    "status": "succeeded",
                    "stage": result.stage or "done",
                    "error": None,
                    "input_pdf": str(result.input_pdf) if result.input_pdf else None,
                    "source_url": url,
                    "marker_markdown": str(result.marker_markdown) if result.marker_markdown else None,
                    "translated_markdown": (
                        str(result.translated_markdown) if result.translated_markdown else None
                    ),
                    "output_markdown": str(result.output_markdown),
                }
            )
            _write_manifest(job_dir, payload)
        except Exception as exc:
            payload.update(
                {
                    "status": "failed",
                    "stage": payload.get("stage") or "failed",
                    "error": str(exc),
                    "source_url": url,
                }
            )
            _write_manifest(job_dir, payload)

    def _default_url_pipeline_runner(
        self,
        url: str,
        *,
        settings: Settings,
        job_dir: Path,
        translator: Optional[BaseTranslator] = None,
    ) -> PipelineResult:
        download_result = download_pdf(
            url=url,
            output_dir=job_dir / "source",
        )
        return self.pipeline_runner(
            download_result.output_path,
            settings=settings,
            job_dir=job_dir,
            translator=translator,
            source_reference=url,
        )

    def get_job(self, job_id: str) -> Dict[str, object]:
        with self._lock:
            job_dir = self._jobs.get(job_id, self.settings.jobs_dir / job_id)
        return _read_manifest(job_dir)


def create_app(
    *,
    settings: Settings,
    pipeline_runner: Callable[..., PipelineResult] = run_file_pipeline,
    url_pipeline_runner: Optional[Callable[..., PipelineResult]] = None,
    translator: Optional[BaseTranslator] = None,
) -> Flask:
    app = Flask(__name__)
    job_manager = JobManager(
        settings=settings,
        pipeline_runner=pipeline_runner,
        url_pipeline_runner=url_pipeline_runner,
        translator=translator,
        max_workers=1,
    )
    app.config["JOB_MANAGER"] = job_manager
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_mb * 1024 * 1024

    @app.get("/")
    def index():
        return render_template_string(_INDEX_HTML)

    @app.post("/api/jobs/pdf")
    def create_pdf_job():
        uploaded = request.files.get("file")
        if uploaded is None or not uploaded.filename:
            return jsonify({"error": "missing pdf file"}), 400
        if not uploaded.filename.lower().endswith(".pdf"):
            return jsonify({"error": "only .pdf uploads are supported"}), 400

        job_id = job_manager.submit_pdf(uploaded.filename, uploaded.read())
        status = job_manager.get_job(job_id)
        return jsonify(status), 202

    @app.post("/api/jobs/url")
    def create_url_job():
        payload = request.get_json(silent=True) or {}
        url = str(payload.get("url") or "").strip()
        if not url:
            return jsonify({"error": "missing pdf url"}), 400
        if not re.match(r"^https?://", url, re.I):
            return jsonify({"error": "url must start with http:// or https://"}), 400
        if ".pdf" not in url.lower():
            return jsonify({"error": "url must point to a pdf resource"}), 400

        job_id = job_manager.submit_url(url)
        status = job_manager.get_job(job_id)
        return jsonify(status), 202

    @app.get("/api/jobs/<job_id>")
    def get_job(job_id: str):
        try:
            return jsonify(job_manager.get_job(job_id))
        except JobError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.get("/api/jobs/<job_id>/download/md")
    def download_markdown(job_id: str):
        try:
            status = job_manager.get_job(job_id)
        except JobError as exc:
            return jsonify({"error": str(exc)}), 404
        path = status.get("translated_markdown")
        if not path:
            return jsonify({"error": "markdown output not ready"}), 404
        return send_file(path, as_attachment=True)

    @app.errorhandler(PDFTranslateError)
    def handle_domain_error(exc: PDFTranslateError):
        return jsonify({"error": str(exc), "code": exit_code_for(exc)}), 500

    return app


def serve_app(
    *,
    settings: Settings,
    pipeline_runner: Callable[..., PipelineResult] = run_file_pipeline,
    translator: Optional[BaseTranslator] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> None:
    app = create_app(settings=settings, pipeline_runner=pipeline_runner, translator=translator)
    app.run(host=host or settings.web_host, port=port or settings.web_port)
