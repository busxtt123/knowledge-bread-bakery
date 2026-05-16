#!/usr/bin/env python3
"""
Convert source material into Markdown for the knowledge-bread workflow.

Usage:
    python scripts/convert-source-to-md.py SOURCE_PATH OUTPUT.md

Dependencies:
    pip install "markitdown[all]"

Notes:
    Plain .md/.markdown/.txt files are copied into normalized Markdown.
    Other supported formats are delegated to Microsoft MarkItDown.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import venv
from pathlib import Path


PLAIN_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
PDF_SUFFIXES = {".pdf"}
DEPENDENCY = "markitdown[all]"
BOOTSTRAP_ENV = "KBM_MARKITDOWN_BOOTSTRAPPED"
EXTRAS_BOOTSTRAP_ENV = "KBM_MARKITDOWN_EXTRAS_BOOTSTRAPPED"
MIN_PDF_VISIBLE_CHARS = 1200
MIN_PDF_LONG_TEXT_LINES = 3


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def runtime_python() -> Path:
    root = skill_root() / ".skill-runtime" / "markitdown-venv"
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def install_markitdown(py: Path) -> None:
    subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(py), "-m", "pip", "install", DEPENDENCY], check=True)


def require_markitdown():
    try:
        from markitdown import MarkItDown  # type: ignore
    except ModuleNotFoundError as exc:
        if os.environ.get(BOOTSTRAP_ENV) == "1":
            raise SystemExit(
                "MarkItDown is still missing after bootstrap.\n"
                "Install manually in the local runtime:\n"
                f"  {runtime_python()} -m pip install {DEPENDENCY}"
            ) from exc

        py = runtime_python()
        venv_dir = py.parents[1]
        if not py.exists():
            print(f"Creating local MarkItDown runtime: {venv_dir}", file=sys.stderr)
            venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
        else:
            result = subprocess.run([str(py), "-c", "import markitdown"], capture_output=True)
            if result.returncode == 0:
                env = os.environ.copy()
                env[BOOTSTRAP_ENV] = "1"
                os.execvpe(str(py), [str(py), __file__, *sys.argv[1:]], env)

        print(
            "Installing MarkItDown inside the skill runtime.",
            file=sys.stderr,
        )
        install_markitdown(py)
        env = os.environ.copy()
        env[BOOTSTRAP_ENV] = "1"
        os.execvpe(str(py), [str(py), __file__, *sys.argv[1:]], env)
    return MarkItDown


def copy_plain_text(source: Path, output: Path) -> None:
    text = source.read_text(encoding="utf-8", errors="replace")
    output.write_text(text, encoding="utf-8")


def visible_chars(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "", text)


def long_text_line_count(text: str) -> int:
    count = 0
    for line in text.replace("\f", "\n").splitlines():
        compact = visible_chars(line)
        if len(compact) >= 35:
            count += 1
    return count


def validate_pdf_text(text: str, source: Path) -> None:
    visible_count = len(visible_chars(text))
    long_lines = long_text_line_count(text)
    if visible_count >= MIN_PDF_VISIBLE_CHARS and long_lines >= MIN_PDF_LONG_TEXT_LINES:
        return

    raise SystemExit(
        "PDF 默认抽取没有得到足够的连续正文。\n"
        f"来源：{source}\n"
        f"可见字符数：{visible_count}；连续正文行数：{long_lines}。\n"
        "这通常说明 PDF 是扫描件 / 图片页，或 MarkItDown 只抽到了元信息、封面、目录。\n"
        "不要把这次结果当成资料。请改用 OCR fallback：\n"
        f"  python scripts/ocr-pdf-to-md.py {source!s} OUTPUT.md\n"
        "OCR 完成后仍要抽样读正文，确认可读后再进入验料。"
    )


def convert_with_markitdown(source: Path, output: Path) -> None:
    MarkItDown = require_markitdown()
    converter = MarkItDown()
    try:
        result = converter.convert(str(source))
    except Exception as exc:
        message = str(exc)
        missing_optional = (
            "MissingDependencyException" in message
            or "optional dependency" in message
            or "dependencies needed" in message
        )
        if missing_optional and os.environ.get(EXTRAS_BOOTSTRAP_ENV) != "1":
            py = runtime_python()
            if not py.exists():
                venv.EnvBuilder(with_pip=True, clear=False).create(py.parents[1])
            print("Installing MarkItDown optional dependencies.", file=sys.stderr)
            install_markitdown(py)
            env = os.environ.copy()
            env[BOOTSTRAP_ENV] = "1"
            env[EXTRAS_BOOTSTRAP_ENV] = "1"
            os.execvpe(str(py), [str(py), __file__, *sys.argv[1:]], env)
        raise
    text = getattr(result, "text_content", None)
    if not text:
        raise SystemExit(f"MarkItDown returned no text for: {source}")
    if source.suffix.lower() in PDF_SUFFIXES:
        validate_pdf_text(text, source)
    output.write_text(text, encoding="utf-8")


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print("Usage: python scripts/convert-source-to-md.py SOURCE_PATH OUTPUT.md")
        return 0

    if len(sys.argv) != 3:
        print("Usage: python scripts/convert-source-to-md.py SOURCE_PATH OUTPUT.md", file=sys.stderr)
        return 2

    source_arg = sys.argv[1]
    output = Path(sys.argv[2]).expanduser().resolve()

    source = Path(source_arg).expanduser().resolve()

    if not source.exists():
        print(f"Source not found: {source}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)

    if source.is_dir():
        print("Directory conversion is intentionally explicit: pass one source file at a time.", file=sys.stderr)
        return 2

    if source.suffix.lower() in PLAIN_TEXT_SUFFIXES:
        copy_plain_text(source, output)
    else:
        convert_with_markitdown(source, output)

    if output.stat().st_size == 0:
        print(f"Converted Markdown is empty: {output}", file=sys.stderr)
        return 1

    print(f"Markdown generated: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
