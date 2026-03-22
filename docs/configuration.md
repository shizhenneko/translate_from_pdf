# Configuration

本项目已经将在线模型配置统一抽象为 `LLM_*`，不再要求用户使用 `OPENAI_*` 命名。

## Required

在线翻译模式下，以下变量是必须的：

```dotenv
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

含义：

- `LLM_API_KEY`：模型服务密钥
- `LLM_BASE_URL`：兼容接口基础地址
- `LLM_MODEL`：模型 ID

## Optional

```dotenv
PDF_TRANSLATE_CACHE_DIR=.cache/pdf_translate
PDF_TRANSLATE_JOBS_DIR=.jobs/pdf_translate
PDF_TRANSLATE_CJK_FONT_PATH=
PDF_TRANSLATE_MATH_FONT_PATH=
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

## Notes

- 当前实现使用 `openai` Python SDK 访问兼容接口，这是实现细节，不代表你必须使用 OpenAI 平台。
- 只要服务端提供兼容的 Chat Completions 接口，通常都可以通过 `LLM_BASE_URL + LLM_MODEL` 接入。
- 如果以后要支持非 OpenAI-compatible 协议，再引入 `LLM_PROVIDER` 一类字段会更合理；当前阶段先不增加无实际用途的配置项。
