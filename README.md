# translate_from_pdf

<div align="center">

将 PDF 翻译成结构尽量保真的中文 Markdown。  
适合论文、课程讲义、技术文档、本地知识整理。

[快速开始](#快速开始) · [使用方式](#使用方式) · [配置说明](#配置说明) · [开发](#开发) · [路线图](#路线图)

</div>

---

## Overview

`translate_from_pdf` 是一个面向中文工作流的 PDF 翻译工具，提供 CLI 与本地 Web UI 两种入口。当前主链路为：

```text
PDF / URL
  -> Marker 提取 Markdown
  -> 分段与公式保护
  -> 可配置 LLM 翻译
  -> 中文 Markdown 输出
```

它不是“把 PDF 粗暴转成纯文本再翻译”的脚本，而是尽量保留结构、标题层级、公式、链接和 Markdown 语义，方便后续继续编辑、发布或纳入知识库。

仓库地址：`https://github.com/shizhenneko/translate_from_pdf.git`

## Why This Project

很多 PDF 翻译工具的问题并不在“能不能翻”，而在“翻完还能不能用”。

这个项目的目标是：

- 尽量保留 Markdown 结构，而不是导出一坨难以整理的文本
- 对公式、符号密集段落做保护，避免 LLM 误改数学内容
- 同时支持本地文件和远程 PDF URL
- 让命令行用户和普通用户都能快速上手
- 把运行缓存、任务目录、虚拟环境、`.env` 等本地文件隔离出版本库

## Highlights

| 能力 | 说明 |
| --- | --- |
| 本地 PDF 上传 | 直接上传单个 PDF，创建异步任务 |
| URL 下载处理 | 输入 PDF 直链后自动下载并处理 |
| Markdown 优先 | 输出中文 Markdown，便于继续编辑 |
| 公式保护 | 尽量保留数学公式、符号与占位片段 |
| LLM 可配置 | 使用 `LLM_*` 变量接入兼容接口 |
| 本地 Web UI | 适合快速试用与演示 |
| 离线调试模式 | 可使用 fake translator 做本地回归 |
| Windows / WSL 启动脚本 | 降低环境启动门槛 |

## Project Snapshot

```text
.
├─ pdf_translate/           # 核心包：CLI、Web、管线、翻译器、OCR/解析适配
├─ tests/                   # pytest 测试
├─ docs/configuration.md    # 配置说明
├─ pdf-url-to-zh-pdf.md     # 需求与方案文档
├─ .env.example             # 环境变量模板
├─ start_wsl.sh             # WSL 一键启动
├─ start_windows.ps1        # Windows PowerShell 一键启动
├─ start_windows.bat        # Windows CMD 一键启动
└─ README.md
```

当前仓库已经配置好 `.gitignore`，以下内容默认不会被误提交：

- `.env`
- `.venv` / `.venv-windows` / 本地虚拟环境
- `.cache/`
- `.jobs/`
- `pdfs/`
- 生成的 PDF 与 Markdown 产物

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/shizhenneko/translate_from_pdf.git
cd translate_from_pdf
```

### 2. 创建虚拟环境

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

### 3. 安装依赖

```bash
python -m pip install -U pip
python -m pip install -e .[dev]
```

如果你要跑完整 PDF 提取链路，建议额外安装：

```bash
python -m pip install marker-pdf
```

### 4. 配置环境变量

```bash
cp .env.example .env
```

最小必填配置：

```dotenv
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

### 5. 启动并验证

命令行检查：

```bash
python -m pdf_translate --help
```

启动本地 Web UI：

```bash
python -m pdf_translate serve
```

默认访问地址：

```text
http://127.0.0.1:10001/
```

## 使用方式

### CLI

本地 PDF -> 中文 Markdown：

```bash
python -m pdf_translate run --in /path/to/file.pdf
```

指定输出路径：

```bash
python -m pdf_translate run --in /path/to/file.pdf --out output/result.zh.md
```

本地 Markdown -> 中文 Markdown：

```bash
python -m pdf_translate translate-md --in docs/source.md --out output/source.zh.md
```

URL 模式：

```bash
python -m pdf_translate run --url https://example.com/file.pdf
```

离线假翻译模式：

```bash
python -m pdf_translate run --in /path/to/file.pdf --use-fake-translator
python -m pdf_translate translate-md --in docs/source.md --use-fake-translator
```

### Web UI

本地 Web UI 适合非命令行用户或快速演示，支持：

- 上传单个 PDF
- 输入 PDF URL 自动下载
- 异步任务状态轮询
- 完成后下载中文 Markdown

相关接口：

- `POST /api/jobs/pdf`
- `POST /api/jobs/url`
- `GET /api/jobs/<job_id>`
- `GET /api/jobs/<job_id>/download/md`

## 配置说明

完整配置见 [docs/configuration.md](docs/configuration.md)。

常用变量如下：

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

说明：

- 真实在线翻译模式下，`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 必填
- 当前实现通过 `openai` Python SDK 调用兼容接口，但配置命名已经去品牌化
- 如果以后接入非 OpenAI-compatible 协议，再考虑引入 `LLM_PROVIDER`
- `.env` 已被忽略，不会进入 Git

## 系统依赖

### WSL / Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils fonts-wqy-zenhei
```

### Windows

- Python `3.10+`
- 可正常创建虚拟环境
- 若需完整解析链路，请保证 `marker-pdf` 及其依赖可用

## 一键启动

### WSL

```bash
bash ./start_wsl.sh
```

自定义端口：

```bash
bash ./start_wsl.sh 10002
```

### Windows PowerShell

```powershell
.\start_windows.ps1
```

自定义端口：

```powershell
.\start_windows.ps1 -Port 10002
```

### Windows CMD

```bat
start_windows.bat
```

说明：

- `start_wsl.sh` 使用 `.venv`
- `start_windows.ps1` 与 `start_windows.bat` 使用 `.venv-windows`
- WSL 与 Windows 各自独立运行，不共享虚拟环境

## 输出结构

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

## 开发

运行默认离线测试：

```bash
pytest -q -m "not e2e_live"
```

仅检查 CLI 入口：

```bash
python -m pdf_translate --help
```

检查输出文件前 60 行：

```bash
head -n 60 <output>.zh.md
```

开发约定：

- 使用 `pytest`
- 外部模型调用应被 mock，不依赖真实网络
- 每次管线阶段调整都应补回归测试
- 生成产物不要进入版本库

## Design Notes

- `Marker` 是当前主解析路径
- 数学公式、变量名、符号密集内容优先透传保护
- 表格、代码块、链接等内容尽量保留 Markdown 语义
- Web UI 保持轻量，核心逻辑仍集中在 Python 管线层

## 路线图

- 更细粒度的任务进度展示
- 多文件批量处理
- 双语对照输出
- 更稳定的扫描件 OCR 回退策略
- 更完整的历史任务与预览能力

## License

当前仓库尚未补充正式许可证文件。  
如果你准备公开发布，建议尽快增加 `LICENSE`。
