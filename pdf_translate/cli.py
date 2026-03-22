"""CLI entrypoints."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from .config import configure_logging, load_settings
from .errors import PDFTranslateError, exit_code_for
from .pipeline import run_file_pipeline, run_markdown_translation, run_pipeline
from .translator import FakeTranslator
from .web import serve_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf_translate",
        description="Translate PDFs into Chinese markdown outputs",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the PDF translation pipeline")
    run_parser.add_argument("--url", default=None, help="Source PDF URL (legacy compatibility)")
    run_parser.add_argument("--in", dest="input_pdf", type=Path, default=None, help="Local PDF path")
    run_parser.add_argument("--out", type=Path, default=None, help="Optional output Markdown path")
    run_parser.add_argument("--job-dir", type=Path, default=None, help="Optional job directory")
    run_parser.add_argument("--env-file", default=".env", help="Path to .env file")
    run_parser.add_argument(
        "--use-fake-translator",
        action="store_true",
        help="Use local fake translator (offline testing only)",
    )
    run_parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Legacy option for URL mode; currently ignored by the Marker pipeline",
    )

    translate_md_parser = subparsers.add_parser(
        "translate-md",
        help="Translate a local markdown file into Chinese markdown",
    )
    translate_md_parser.add_argument("--in", dest="input_markdown", type=Path, required=True)
    translate_md_parser.add_argument("--out", type=Path, default=None)
    translate_md_parser.add_argument("--env-file", default=".env", help="Path to .env file")
    translate_md_parser.add_argument(
        "--use-fake-translator",
        action="store_true",
        help="Use local fake translator (offline testing only)",
    )

    serve_parser = subparsers.add_parser("serve", help="Start the local web UI")
    serve_parser.add_argument("--host", default=None, help="Bind host")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port")
    serve_parser.add_argument("--env-file", default=".env", help="Path to .env file")
    serve_parser.add_argument(
        "--use-fake-translator",
        action="store_true",
        help="Use local fake translator (offline testing only)",
    )

    return parser


def _build_fake_translator_if_needed(enabled: bool):
    return FakeTranslator() if enabled else None


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        raise SystemExit(0)

    configure_logging()
    try:
        require_online = not getattr(args, "use_fake_translator", False)
        settings = load_settings(
            env_file=args.env_file,
            require_online=require_online,
        )
        translator = _build_fake_translator_if_needed(getattr(args, "use_fake_translator", False))

        if args.command == "run":
            if args.input_pdf and args.url:
                raise SystemExit("Specify either --in or --url, not both")
            if not args.input_pdf and not args.url:
                raise SystemExit("run requires either --in <pdf> or --url <pdf-url>")

            if args.url:
                result = run_pipeline(
                    url=args.url,
                    settings=settings,
                    output_path=args.out,
                    max_pages=args.max_pages,
                    translator=translator,
                )
            else:
                result = run_file_pipeline(
                    args.input_pdf,
                    settings=settings,
                    job_dir=args.job_dir,
                    translator=translator,
                    output_markdown_path=args.out,
                )

            print("Output Markdown: %s" % result.output_markdown)
            if result.translated_markdown:
                print("Stored Markdown: %s" % result.translated_markdown)
            return

        if args.command == "translate-md":
            output_path = run_markdown_translation(
                args.input_markdown,
                settings=settings,
                output_path=args.out,
                translator=translator,
            )
            print("Output Markdown: %s" % output_path)
            return

        if args.command == "serve":
            serve_app(
                settings=settings,
                translator=translator,
                host=args.host,
                port=args.port,
            )
            return

        parser.print_help()
        raise SystemExit(0)
    except PDFTranslateError as exc:
        print("ERROR: %s" % exc)
        raise SystemExit(exit_code_for(exc))


if __name__ == "__main__":
    main()
