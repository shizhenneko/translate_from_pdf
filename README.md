# translate_from_pdf

一个面向中文工作流的 PDF 翻译工具，提供 CLI 与本地 Web UI 两种入口。当前主链路为：

`PDF / URL -> Marker 提取 Markdown -> 分段保护公式与结构 -> 可配置 LLM 翻译 -> 中文 Markdown 输出`

仓库地址：`https://github.com/shizhenneko/translate_from_pdf.git`

## Features

- 支持本地 PDF 上传，或直接输入 PDF URL 自动下载处理
- 支持 `Marker -> Markdown -> 翻译` 的稳定主链路
- 默认输出中文 Markdown，便于二次编辑、发布和版本管理
- 支持可配置的 LLM 接口，当前默认适配 OpenAI-compatible 网关
- 提供本地 Web UI，适合非命令行用户快速试用
- 提供离线假翻译模式，便于调试与回归测试
- 提供 WSL、Windows PowerShell、Windows CMD 启动脚本

## Preview

当前 Web UI 支持：

- 上传单个 PDF 文件
- 输入 PDF 直链并创建异步任务
- 实时查看任务状态、阶段与错误信息
- 在任务完成后直接下载中文 Markdown

## Project Structure

```text
.
├─ pdf_translate/           # 核心包：CLI、Web、管线、翻译器、OCR/解析适配
├─ tests/                   # pytest 测试
├─ pdf-url-to-zh-pdf.md     # 需求与方案文档
├─ start_wsl.sh             # WSL 一键启动
├─ start_windows.ps1        # Windows PowerShell 一键启动
├─ start_windows.bat        # Windows CMD 一键启动
├─ .env.example             # 环境变量模板
└─ README.md
```

运行时产生的缓存、任务目录、翻译结果、PDF 产物、虚拟环境与本地密钥均已通过 `.gitignore` 排除，不会被误提交。

## Quick Start

### 1. 克隆仓库

```bash
git clone https://github.com/shizhenneko/translate_from_pdf.git
cd translate_from_pdf
```

### 2. 创建虚拟环境

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

如果你要运行真实 PDF 提取链路，建议额外安装：

```bash
python -m pip install marker-pdf
```

### 4. 配置环境变量

```bash
cp .env.example .env
```

然后填写你的 API 配置。

## Environment Variables

完整配置说明可见 [docs/configuration.md](/mnt/c/Users/86159/Desktop/translate_from_pdf/docs/configuration.md)。

最小可运行配置如下：

```dotenv
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

常用可选项：

```dotenv
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

- 如果使用真实在线翻译，必须配置 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`
- 当前代码默认通过 `openai` Python SDK 访问兼容接口，但环境变量命名不再绑定 OpenAI 品牌
- `.env` 已被忽略，不会进入 Git
- Windows 下字体路径可按需补充 `PDF_TRANSLATE_CJK_FONT_PATH` 与 `PDF_TRANSLATE_MATH_FONT_PATH`

## System Dependencies

### WSL / Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils fonts-wqy-zenhei
```

### Windows

- Python `3.10+`
- 可正常创建虚拟环境
- 如需完整 PDF 解析链路，请保证 `marker-pdf` 及其依赖可用

## Usage

### CLI: 本地 PDF -> 中文 Markdown

```bash
python -m pdf_translate run --in /path/to/file.pdf
```

指定输出路径：

```bash
python -m pdf_translate run --in /path/to/file.pdf --out output/result.zh.md
```

### CLI: 本地 Markdown -> 中文 Markdown

```bash
python -m pdf_translate translate-md --in docs/source.md --out output/source.zh.md
```

### CLI: URL 模式

```bash
python -m pdf_translate run --url https://example.com/file.pdf
```

### CLI: 离线假翻译模式

```bash
python -m pdf_translate run --in /path/to/file.pdf --use-fake-translator
python -m pdf_translate translate-md --in docs/source.md --use-fake-translator
```

## Web UI

启动本地服务：

```bash
python -m pdf_translate serve
```

默认访问地址：

```text
http://127.0.0.1:10001/
```

支持的接口：

- `POST /api/jobs/pdf`：上传 PDF 创建任务
- `POST /api/jobs/url`：提交 PDF URL 创建任务
- `GET /api/jobs/<job_id>`：查询任务状态
- `GET /api/jobs/<job_id>/download/md`：下载中文 Markdown

## One-Click Launch

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

### 运行测试

默认离线测试：

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

### 测试约定

- 使用 `pytest`
- 外部模型调用应被 mock，不依赖真实网络
- 每个管线阶段变更都应带回归测试

## Design Notes

- `Marker` 是当前主解析路径
- 数学公式、符号密集内容优先走保护与透传策略
- 表格、代码块、链接等结构尽量保留 Markdown 语义
- Web UI 保持轻量，核心逻辑仍以 Python 管线为中心

## Roadmap

- 更细粒度的任务进度展示
- 多文件批量处理
- 输出双语对照版本
- 更稳定的扫描件 OCR 回退策略
- 更完整的结果预览与历史任务管理

## License

如需开源发布，建议尽快补充正式许可证文件。
