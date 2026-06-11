#!/usr/bin/env python3
"""
Convert source material into Markdown for the knowledge-bread workflow.

Usage:
    python scripts/convert-source-to-md.py SOURCE_PATH OUTPUT.md

Dependencies:
    The script installs an isolated MarkItDown runtime when needed.

Notes:
    Plain .md/.markdown/.txt files are copied into normalized Markdown.
    EPUB files use the standard library path first, avoiding optional runtime
    failures on Windows.
    Other supported formats are delegated to Microsoft MarkItDown.
"""

from __future__ import annotations

import os
import posixpath
import re
import subprocess
import sys
import venv
import zipfile
from html.parser import HTMLParser
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


configure_stdio()


PLAIN_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
PDF_SUFFIXES = {".pdf"}
EPUB_SUFFIXES = {".epub"}
MARKITDOWN_DEPENDENCIES = (
    "markitdown",
    # Curated local-document extras. Avoid markitdown[all]: on newer Python
    # versions it can backtrack into old releases and pull online/media deps
    # this skill intentionally does not use.
    "lxml",
    "mammoth",
    "olefile",
    "openpyxl",
    "pandas",
    "pdfminer-six",
    "pdfplumber",
    "python-pptx",
    "xlrd",
)
DEPENDENCY_LABEL = " ".join(MARKITDOWN_DEPENDENCIES)
MIN_MARKITDOWN_VERSION = (0, 1, 5)
BOOTSTRAP_ENV = "KBM_MARKITDOWN_BOOTSTRAPPED"
EXTRAS_BOOTSTRAP_ENV = "KBM_MARKITDOWN_EXTRAS_BOOTSTRAPPED"
RUNTIME_ENV = "KBM_MARKITDOWN_VENV"
MIN_PDF_VISIBLE_CHARS = 1200
MIN_PDF_LONG_TEXT_LINES = 3
MIN_PDF_HIGH_CONFIDENCE_VISIBLE_CHARS = 6000


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def runtime_dir() -> Path:
    override = os.environ.get(RUNTIME_ENV)
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP")
        if base:
            py_tag = f"py{sys.version_info.major}{sys.version_info.minor}"
            return Path(base) / "knowledge-bread-bakery" / f"markitdown-venv-{py_tag}"

    return skill_root() / ".skill-runtime" / "markitdown-venv"


def runtime_python() -> Path:
    root = runtime_dir()
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def run_checked(args: list[str], failure_message: str) -> None:
    result = subprocess.run(args)
    if result.returncode != 0:
        raise SystemExit(
            failure_message
            + "\nCommand failed:\n  "
            + " ".join(args)
            + f"\nExit code: {result.returncode}"
        )


def install_markitdown(py: Path) -> None:
    run_checked(
        [str(py), "-m", "pip", "install", "--upgrade", "pip"],
        "MarkItDown runtime pip upgrade failed.",
    )
    run_checked(
        [str(py), "-m", "pip", "install", "--upgrade", *MARKITDOWN_DEPENDENCIES],
        "MarkItDown dependency installation failed.",
    )


def version_tuple(raw: str) -> tuple[int, ...]:
    parts = []
    for part in re.split(r"[^\d]+", raw):
        if part:
            parts.append(int(part))
    return tuple(parts) or (0,)


def markitdown_version_ok() -> bool:
    try:
        return version_tuple(metadata.version("markitdown")) >= MIN_MARKITDOWN_VERSION
    except metadata.PackageNotFoundError:
        return False


def runtime_has_markitdown(py: Path) -> bool:
    if not py.exists():
        return False
    probe = (
        "import importlib.metadata as m, re\n"
        "v=m.version('markitdown')\n"
        "parts=tuple(int(p) for p in re.split(r'[^0-9]+', v) if p)\n"
        f"raise SystemExit(0 if parts >= {MIN_MARKITDOWN_VERSION!r} else 1)\n"
    )
    result = subprocess.run([str(py), "-c", probe], capture_output=True)
    return result.returncode == 0


def run_in_runtime(py: Path, *, extras_bootstrapped: bool = False) -> None:
    env = os.environ.copy()
    env[BOOTSTRAP_ENV] = "1"
    if extras_bootstrapped:
        env[EXTRAS_BOOTSTRAP_ENV] = "1"
    result = subprocess.run([str(py), __file__, *sys.argv[1:]], env=env)
    raise SystemExit(result.returncode)


def require_markitdown():
    missing_reason = "missing Python package: markitdown"
    try:
        from markitdown import MarkItDown  # type: ignore
        if markitdown_version_ok():
            return MarkItDown
        try:
            installed = metadata.version("markitdown")
        except metadata.PackageNotFoundError:
            installed = "unknown"
        missing_reason = f"MarkItDown version {installed} is older than required"
    except ModuleNotFoundError:
        pass

    if os.environ.get(BOOTSTRAP_ENV) == "1":
        raise SystemExit(
            f"MarkItDown is still unavailable after bootstrap: {missing_reason}.\n"
            "Install manually in the local runtime:\n"
            f"  {runtime_python()} -m pip install {DEPENDENCY_LABEL}"
        )

    py = runtime_python()
    venv_dir = py.parents[1]
    if not py.exists():
        print(f"Creating local MarkItDown runtime: {venv_dir}", file=sys.stderr)
        venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
    elif runtime_has_markitdown(py):
        run_in_runtime(py)

    print(
        "Installing MarkItDown inside the skill runtime.",
        file=sys.stderr,
    )
    install_markitdown(py)
    run_in_runtime(py)


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


class EpubHtmlTextExtractor(HTMLParser):
    block_tags = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
    skip_tags = {"head", "script", "style", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.heading_level: int | None = None

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        tag = tag.lower()
        if tag in self.skip_tags:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self.block_tags:
            self.parts.append("\n")
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.heading_level = int(tag[1])
            self.parts.append("#" * min(self.heading_level, 6) + " ")
        elif tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.skip_tags:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag in self.block_tags:
            self.parts.append("\n")
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.heading_level = None

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts).replace("\ufeff", "")
        lines = []
        blank = False
        for line in raw.replace("\r", "\n").splitlines():
            compact = re.sub(r"[ \t\f\v]+", " ", line).strip()
            if not compact:
                if lines and not blank:
                    lines.append("")
                    blank = True
                continue
            lines.append(compact)
            blank = False
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines) + "\n"


def epub_join(base_dir: str, href: str) -> str:
    href = unquote(href.split("#", 1)[0])
    path = posixpath.normpath(posixpath.join(base_dir, href))
    if path == "." or path.startswith("../") or path.startswith("/"):
        raise ValueError(f"Unsafe EPUB href: {href}")
    return path


def epub_title(opf_root: ET.Element) -> str | None:
    for elem in opf_root.findall(".//{*}metadata/{*}title"):
        if elem.text and elem.text.strip():
            return elem.text.strip()
    for elem in opf_root.findall(".//{*}title"):
        if elem.text and elem.text.strip():
            return elem.text.strip()
    return None


def extract_epub_text(source: Path) -> str:
    with zipfile.ZipFile(source) as book:
        try:
            container_xml = book.read("META-INF/container.xml")
        except KeyError as exc:
            raise SystemExit(f"EPUB missing META-INF/container.xml: {source}") from exc

        container = ET.fromstring(container_xml)
        rootfile = container.find(".//{*}rootfile")
        if rootfile is None or not rootfile.attrib.get("full-path"):
            raise SystemExit(f"EPUB container has no rootfile entry: {source}")

        opf_path = rootfile.attrib["full-path"]
        opf_dir = posixpath.dirname(opf_path)
        opf_root = ET.fromstring(book.read(opf_path))

        manifest: dict[str, tuple[str, str]] = {}
        for item in opf_root.findall(".//{*}manifest/{*}item"):
            item_id = item.attrib.get("id")
            href = item.attrib.get("href")
            if not item_id or not href:
                continue
            media_type = item.attrib.get("media-type", "")
            manifest[item_id] = (epub_join(opf_dir, href), media_type)

        spine_paths: list[str] = []
        for itemref in opf_root.findall(".//{*}spine/{*}itemref"):
            idref = itemref.attrib.get("idref")
            if idref and idref in manifest:
                path, media_type = manifest[idref]
                if media_type in {"application/xhtml+xml", "text/html"} or path.lower().endswith(
                    (".xhtml", ".html", ".htm")
                ):
                    spine_paths.append(path)

        if not spine_paths:
            spine_paths = [
                path
                for path, media_type in manifest.values()
                if media_type in {"application/xhtml+xml", "text/html"}
                or path.lower().endswith((".xhtml", ".html", ".htm"))
            ]

        if not spine_paths:
            raise SystemExit(f"EPUB has no readable HTML spine: {source}")

        sections = []
        title = epub_title(opf_root)
        if title:
            sections.append(f"# {title}\n")

        seen = set()
        for path in spine_paths:
            if path in seen:
                continue
            seen.add(path)
            try:
                html_text = book.read(path).decode("utf-8-sig", errors="replace")
            except KeyError:
                continue
            parser = EpubHtmlTextExtractor()
            parser.feed(html_text)
            text = parser.text().strip()
            if text:
                sections.append(text)

    text = "\n\n".join(sections).strip() + "\n"
    if len(visible_chars(text)) < 400:
        raise SystemExit(
            "EPUB 转换后正文过短，可能只抽到了目录、封面或元信息。\n"
            f"来源：{source}\n"
            f"可见字符数：{len(visible_chars(text))}。\n"
            "请抽样检查 EPUB，或请顾客提供 Markdown / TXT / PDF 正文副本。"
        )
    return text


def convert_epub(source: Path, output: Path) -> None:
    text = extract_epub_text(source)
    output.write_text(text, encoding="utf-8")


def validate_pdf_text(text: str, source: Path) -> None:
    visible_count = len(visible_chars(text))
    long_lines = long_text_line_count(text)
    if visible_count >= MIN_PDF_VISIBLE_CHARS and long_lines >= MIN_PDF_LONG_TEXT_LINES:
        return
    if visible_count >= MIN_PDF_HIGH_CONFIDENCE_VISIBLE_CHARS:
        print(
            "Warning: PDF 抽取到了较多正文，但换行结构不稳定；请抽样检查段落顺序和可读性。\n"
            f"来源：{source}\n"
            f"可见字符数：{visible_count}；连续正文行数：{long_lines}。",
            file=sys.stderr,
        )
        return

    raise SystemExit(
        "PDF 默认抽取没有得到足够的连续正文。\n"
        f"来源：{source}\n"
        f"可见字符数：{visible_count}；连续正文行数：{long_lines}。\n"
        "这通常说明 PDF 是扫描件 / 图片页，或 MarkItDown 只抽到了元信息、封面、目录。\n"
        "不要把这次结果当成资料。请改用 OCR fallback：\n"
        "  python scripts/ocr-pdf-to-md.py SOURCE.pdf OUTPUT.md\n"
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
            run_in_runtime(py, extras_bootstrapped=True)
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

    suffix = source.suffix.lower()

    if suffix in PLAIN_TEXT_SUFFIXES:
        copy_plain_text(source, output)
    elif suffix in EPUB_SUFFIXES:
        convert_epub(source, output)
    else:
        convert_with_markitdown(source, output)

    if output.stat().st_size == 0:
        print(f"Converted Markdown is empty: {output}", file=sys.stderr)
        return 1

    print(f"Markdown generated: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
