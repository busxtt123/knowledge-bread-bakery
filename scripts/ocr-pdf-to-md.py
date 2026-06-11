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
import os
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


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


configure_stdio()


def add_path_dir(path: Path) -> None:
    path_text = str(path)
    paths = os.environ.get("PATH", "").split(os.pathsep)
    if path_text not in paths:
        os.environ["PATH"] = path_text + os.pathsep + os.environ.get("PATH", "")


def local_tessdata_dir() -> Path | None:
    if os.name != "nt":
        return None
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP")
    if not base:
        return None
    return Path(base) / "knowledge-bread-bakery" / "tessdata"


def add_windows_ocr_paths() -> None:
    if os.name != "nt":
        return

    candidates: list[Path] = []
    env_roots = {
        name: Path(value)
        for name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA", "USERPROFILE")
        if (value := os.environ.get(name))
    }

    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        root = env_roots.get(key)
        if root:
            candidates.append(root / "Tesseract-OCR" / "tesseract.exe")
            candidates.extend(root.glob("Poppler*/Library/bin/pdftoppm.exe"))
            candidates.extend(root.glob("poppler*/Library/bin/pdftoppm.exe"))

    local = env_roots.get("LOCALAPPDATA")
    if local:
        candidates.append(local / "Programs" / "Tesseract-OCR" / "tesseract.exe")
        candidates.append(local / "Microsoft" / "WinGet" / "Links" / "tesseract.exe")
        candidates.append(local / "Microsoft" / "WinGet" / "Links" / "pdftoppm.exe")
        candidates.extend(
            local.glob("Microsoft/WinGet/Packages/oschwartz10612.Poppler_*/*/Library/bin/pdftoppm.exe")
        )

    profile = env_roots.get("USERPROFILE")
    if profile:
        candidates.append(profile / "scoop" / "apps" / "tesseract" / "current" / "tesseract.exe")
        candidates.append(profile / "scoop" / "apps" / "poppler" / "current" / "bin" / "pdftoppm.exe")

    for exe in candidates:
        if exe.exists():
            add_path_dir(exe.parent)


add_windows_ocr_paths()


def command_path(command: str) -> str:
    return shutil.which(command) or command


def command_args(command: str, *args: str) -> list[str]:
    executable = command_path(command)
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        return ["cmd.exe", "/d", "/c", executable, *args]
    return [executable, *args]


def decode_process_output(output: bytes | str | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def requested_languages(lang: str) -> set[str]:
    return {part for part in lang.split("+") if part}


def local_tessdata_has_languages(lang: str) -> bool:
    tessdata = local_tessdata_dir()
    if not tessdata or not tessdata.exists():
        return False
    requested = requested_languages(lang)
    return bool(requested) and all((tessdata / f"{language}.traineddata").exists() for language in requested)


def configure_windows_tessdata_prefix(lang: str) -> None:
    if os.name != "nt":
        return

    tessdata = local_tessdata_dir()
    if not tessdata:
        return

    tessdata_text = str(tessdata)
    if local_tessdata_has_languages(lang):
        os.environ["TESSDATA_PREFIX"] = tessdata_text
    elif os.environ.get("TESSDATA_PREFIX") == tessdata_text:
        os.environ.pop("TESSDATA_PREFIX", None)


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
        command_args("tesseract", "--list-langs"),
        capture_output=True,
    )
    if result.returncode != 0:
        return set()

    languages: set[str] = set()
    for line in decode_process_output(result.stdout).splitlines():
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
        configure_windows_tessdata_prefix(lang)
        requested = requested_languages(lang)
        available_languages = available_tesseract_languages()
        missing_languages = sorted(requested - available_languages)
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

    add_windows_ocr_paths()
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
        cmd = command_args("pdftoppm", "-r", str(dpi), "-png")
        if first_page is not None:
            cmd.extend(["-f", str(first_page)])
        if last_page is not None:
            cmd.extend(["-l", str(last_page)])
        cmd.extend([str(pdf), str(prefix)])
        render_result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if render_result.returncode != 0:
            raise RuntimeError(decode_process_output(render_result.stderr).strip() or "pdftoppm 未能渲染 PDF 页面")

        images = sorted(Path(tmp).glob("page-*.png"))
        if not images:
            raise RuntimeError("pdftoppm produced no page images")

        pages: list[tuple[int, str]] = []
        for idx, image in enumerate(images, 1):
            page_label = first_page + idx - 1 if first_page is not None else idx
            result = subprocess.run(
                command_args("tesseract", str(image), "stdout", "-l", lang, "--psm", "6"),
                capture_output=True,
            )
            if result.returncode != 0:
                raise RuntimeError(decode_process_output(result.stderr).strip() or f"tesseract failed on page {page_label}")
            text = decode_process_output(result.stdout).strip()
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
