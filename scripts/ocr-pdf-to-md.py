#!/usr/bin/env python3
"""
OCR a scanned PDF into Markdown.

Usage:
    python scripts/ocr-pdf-to-md.py input.pdf output.md
    python scripts/ocr-pdf-to-md.py --install-deps input.pdf output.md

This is the PDF fallback for the skill. It is not the default PDF route.
Readable PDFs should first go through scripts/convert-source-to-md.py
(MarkItDown). Use this script only when the PDF is scanned/image-only or the
default route returns too little readable text.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


MIN_OCR_PAGE_VISIBLE_CHARS = 120
MIN_OCR_TOTAL_VISIBLE_CHARS = 300
OCR_INSTALL_HINT = """Install OCR dependencies before using scanned PDF fallback:
- Ubuntu/Debian: sudo apt-get install poppler-utils tesseract-ocr tesseract-ocr-chi-sim
- macOS/Homebrew: brew install poppler tesseract tesseract-lang
- Windows: install Poppler and Tesseract, then add both bin directories to PATH.
Or run this script with --install-deps to let scripts/setup-ocr-deps.py try the
installation before OCR starts.
"""


def metadata_block(source: Path, method: str) -> str:
    extracted_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return (
        "<!--\n"
        f"source_pdf: {source}\n"
        f"extract_method: {method}\n"
        f"extracted_at: {extracted_at}\n"
        "-->\n\n"
    )


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip() + "\n"


def available_tesseract_languages() -> set[str]:
    result = subprocess.run(
        ["tesseract", "--list-langs"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if result.returncode != 0:
        return set()

    languages: set[str] = set()
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped and not stripped.lower().startswith("list of available languages"):
            languages.add(stripped)
    return languages


def check_ocr_dependencies(lang: str) -> list[str]:
    problems: list[str] = []

    if not shutil.which("pdftoppm"):
        problems.append("missing `pdftoppm` from Poppler")

    if not shutil.which("tesseract"):
        problems.append("missing `tesseract`")
    else:
        requested_languages = {part for part in lang.split("+") if part}
        available_languages = available_tesseract_languages()
        missing_languages = sorted(requested_languages - available_languages)
        if missing_languages:
            problems.append(
                "missing Tesseract language data: " + ", ".join(missing_languages)
            )

    return problems


def require_ocr_dependencies(lang: str) -> None:
    problems = check_ocr_dependencies(lang)
    if problems:
        details = "\n".join(f"- {problem}" for problem in problems)
        raise RuntimeError(
            "OCR environment is not ready:\n"
            f"{details}\n\n"
            f"{OCR_INSTALL_HINT.strip()}"
        )


def install_ocr_dependencies(lang: str) -> None:
    if not check_ocr_dependencies(lang):
        return

    setup_script = Path(__file__).resolve().with_name("setup-ocr-deps.py")
    if not setup_script.exists():
        raise RuntimeError(
            "OCR environment is not ready, and setup-ocr-deps.py was not found.\n\n"
            f"{OCR_INSTALL_HINT.strip()}"
        )

    print("OCR dependencies are missing. Running setup-ocr-deps.py --install ...")
    result = subprocess.run(
        [sys.executable, str(setup_script), "--lang", lang, "--install"],
    )
    if result.returncode != 0:
        raise RuntimeError(
            "OCR dependency installation did not complete. "
            f"setup-ocr-deps.py exited with code {result.returncode}."
        )

    remaining = check_ocr_dependencies(lang)
    if remaining:
        details = "\n".join(f"- {problem}" for problem in remaining)
        raise RuntimeError(
            "OCR dependency installation finished, but the environment is still not ready:\n"
            f"{details}\n\n"
            "If the installer changed PATH, restart the terminal and run OCR again."
        )


def visible_chars(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "", text)


def is_readable_ocr_page(text: str) -> bool:
    visible_count = len(visible_chars(text))
    if visible_count < MIN_OCR_PAGE_VISIBLE_CHARS:
        return False
    return any(len(visible_chars(line)) >= 25 for line in text.splitlines())


def validate_ocr_pages(pages: list[tuple[int, str]]) -> None:
    total_visible = sum(len(visible_chars(text)) for _, text in pages)
    readable_pages = [(page, text) for page, text in pages if is_readable_ocr_page(text)]
    expected_readable_pages = 1 if len(pages) <= 3 else max(1, len(pages) // 5)
    expected_visible = max(MIN_OCR_TOTAL_VISIBLE_CHARS, len(pages) * 60)

    if len(readable_pages) >= expected_readable_pages and total_visible >= expected_visible:
        return

    page_labels = ", ".join(str(page) for page, _ in pages[:5])
    if len(pages) > 5:
        page_labels += ", ..."
    raise RuntimeError(
        "OCR 已运行，但结果还不足以作为可读来源进入验料。\n"
        f"OCR 页数：{len(pages)}（{page_labels}）；"
        f"可读页数：{len(readable_pages)}；可见字符数：{total_visible}。\n"
        "不要把这次结果当成资料。请缩小页码范围、提高 --dpi、调整 --lang，"
        "或请顾客提供更清晰的 PDF / 原始文本。"
    )


def ocr_pdf(pdf: Path, lang: str, dpi: int, first_page: int | None, last_page: int | None) -> str:
    require_ocr_dependencies(lang)

    with tempfile.TemporaryDirectory(prefix="kbm-pdf-ocr-") as tmp:
        prefix = Path(tmp) / "page"
        cmd = ["pdftoppm", "-r", str(dpi), "-png"]
        if first_page is not None:
            cmd.extend(["-f", str(first_page)])
        if last_page is not None:
            cmd.extend(["-l", str(last_page)])
        cmd.extend([str(pdf), str(prefix)])
        render_result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if render_result.returncode != 0:
            raise RuntimeError(render_result.stderr.strip() or "pdftoppm 未能渲染 PDF 页面")

        images = sorted(Path(tmp).glob("page-*.png"))
        if not images:
            raise RuntimeError("pdftoppm produced no page images")

        pages: list[tuple[int, str]] = []
        for idx, image in enumerate(images, 1):
            page_label = first_page + idx - 1 if first_page is not None else idx
            result = subprocess.run(
                ["tesseract", str(image), "stdout", "-l", lang, "--psm", "6"],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or f"tesseract failed on page {page_label}")
            text = result.stdout.strip()
            pages.append((page_label, text))

        validate_ocr_pages(pages)
        parts = [f"<!-- page: {page_label} -->\n\n{text}" for page_label, text in pages]
        return normalize_text("\n\n---\n\n".join(parts))


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR a scanned PDF into Markdown.")
    parser.add_argument("pdf", nargs="?")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--lang", default="chi_sim+eng", help="Tesseract language, default: chi_sim+eng.")
    parser.add_argument("--dpi", type=int, default=220, help="Image DPI for OCR, default: 220.")
    parser.add_argument("--first-page", type=int, default=None, help="First page to OCR, 1-based.")
    parser.add_argument("--last-page", type=int, default=None, help="Last page to OCR, 1-based.")
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check Poppler/Tesseract availability and exit without OCR.",
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Try to install missing OCR system dependencies before running OCR.",
    )
    args = parser.parse_args()

    if args.check_deps:
        problems = check_ocr_dependencies(args.lang)
        if problems:
            print("OCR dependencies are not ready:", file=sys.stderr)
            for problem in problems:
                print(f"- {problem}", file=sys.stderr)
            print(file=sys.stderr)
            print(OCR_INSTALL_HINT.strip(), file=sys.stderr)
            return 1
        print(f"OCR dependencies ready for language setting: {args.lang}")
        return 0

    if not args.pdf or not args.output:
        parser.error("pdf and output are required unless --check-deps is used")

    pdf = Path(args.pdf).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not pdf.exists():
        print(f"ERROR: PDF not found: {pdf}", file=sys.stderr)
        return 1
    if pdf.suffix.lower() != ".pdf":
        print(f"ERROR: expected a .pdf file: {pdf}", file=sys.stderr)
        return 2
    if args.first_page is not None and args.first_page < 1:
        print("ERROR: --first-page must be >= 1", file=sys.stderr)
        return 2
    if args.last_page is not None and args.last_page < 1:
        print("ERROR: --last-page must be >= 1", file=sys.stderr)
        return 2
    if args.first_page is not None and args.last_page is not None and args.last_page < args.first_page:
        print("ERROR: --last-page must be >= --first-page", file=sys.stderr)
        return 2

    try:
        if args.install_deps:
            install_ocr_dependencies(args.lang)
        text = ocr_pdf(pdf, args.lang, args.dpi, args.first_page, args.last_page)
    except Exception as exc:
        print(f"ERROR: PDF OCR failed for {pdf}: {exc}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    method = f"tesseract-ocr:{args.lang}@{args.dpi}dpi"
    output.write_text(metadata_block(pdf, method) + text, encoding="utf-8")
    print(f"Markdown generated: {output} ({method})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
