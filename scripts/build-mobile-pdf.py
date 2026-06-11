#!/usr/bin/env python3
"""
Build a mobile-friendly PDF from Markdown.

Usage:
    python scripts/build-mobile-pdf.py input.md output.pdf [title]

The script keeps the PDF toolchain isolated. On Linux/macOS the runtime stays
under the skill directory by default. On Windows it uses a short LocalAppData
path to avoid long-path failures in virtualenv and pip. No second PDF script is
used.

WeasyPrint is the preferred renderer and defines the visual baseline. On
Windows, WeasyPrint can be installed as a Python package but still fail at
import time because native graphics DLLs are unavailable. In that case this
same script falls back to a ReportLab renderer that mirrors the WeasyPrint
layout choices as closely as ReportLab allows, so delivery keeps a single
maintained PDF exit.
"""

from __future__ import annotations

import contextlib
import html
import io
import os
import re
import subprocess
import sys
import venv
from pathlib import Path


CORE_DEPENDENCIES = ("markdown",)
WEASYPRINT_DEPENDENCIES = ("weasyprint",)
REPORTLAB_DEPENDENCIES = ("reportlab",)
REQUIRED_RUNTIME_DEPENDENCIES = CORE_DEPENDENCIES + REPORTLAB_DEPENDENCIES
OPTIONAL_RUNTIME_DEPENDENCIES = WEASYPRINT_DEPENDENCIES
BOOTSTRAP_ENV = "KBM_PDF_BOOTSTRAPPED"
RUNTIME_ENV = "KBM_PDF_VENV"
FRONT_MATTER_HEADING_RE = re.compile(r"^(发刊词|导论|前言)(?:[:：\s].*)?$")
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
GENERIC_DOCUMENT_TITLE_RE = re.compile(
    r"^(课程正文|正文|最终稿|终稿|交付稿|成品稿|输出稿|文稿|稿件|final(?:\.md)?|"
    r"manuscript|delivery)$",
    re.IGNORECASE,
)
NUMBERED_SECTION_RE = re.compile(
    r"^第\s*[0-9一二三四五六七八九十百]+\s*[讲章节课篇部](?:[:：\s].*)?$"
)
BOOK_EDGE_HEADING_RE = re.compile(
    r"^(发刊词|导论|前言|序言|引言|结语|结课地图|知识地图|后记|"
    r"附录)(?:[:：\s].*)?$"
)


class MarkdownFormatError(ValueError):
    """The input Markdown can render, but its document structure is unsafe."""


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


configure_stdio()


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
            return Path(base) / "knowledge-bread-bakery" / f"pdf-venv-{py_tag}"

    return skill_root() / ".skill-runtime" / "pdf-venv"


def runtime_python() -> Path:
    root = runtime_dir()
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def bootstrap_attempt() -> int:
    try:
        return int(os.environ.get(BOOTSTRAP_ENV, "0"))
    except ValueError:
        return 0


def install_packages(py: Path, packages: tuple[str, ...], *, required: bool) -> None:
    if not packages:
        return
    result = subprocess.run([str(py), "-m", "pip", "install", *packages])
    if required and result.returncode != 0:
        raise SystemExit(
            "PDF runtime dependency installation failed: "
            + " ".join(packages)
            + "\nInstall manually:\n"
            + f"  {py} -m pip install {' '.join(packages)}"
        )
    if not required and result.returncode != 0:
        print(
            "Warning: optional PDF dependency installation failed: "
            + " ".join(packages)
            + ". ReportLab fallback may still work.",
            file=sys.stderr,
        )


def runtime_has_required_dependencies(py: Path) -> bool:
    if not py.exists():
        return False
    probe = "import markdown; import reportlab"
    result = subprocess.run([str(py), "-c", probe], capture_output=True)
    return result.returncode == 0


def run_in_runtime(py: Path, attempt: int) -> None:
    env = os.environ.copy()
    env[BOOTSTRAP_ENV] = str(attempt + 1)
    result = subprocess.run([str(py), __file__, *sys.argv[1:]], env=env)
    raise SystemExit(result.returncode)


def bootstrap_and_reexec(reason: str) -> None:
    attempt = bootstrap_attempt()
    if attempt >= 2:
        raise SystemExit(
            "PDF dependencies are still unavailable after bootstrap.\n"
            f"Reason: {reason}\n"
            "Install manually in the local runtime:\n"
            + f"  {runtime_python()} -m pip install "
            + " ".join(REQUIRED_RUNTIME_DEPENDENCIES)
        )

    py = runtime_python()
    venv_dir = py.parents[1]
    if not py.exists():
        print(f"Creating local PDF runtime: {venv_dir}", file=sys.stderr)
        venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
    elif runtime_has_required_dependencies(py):
        run_in_runtime(py, attempt)

    print(
        "Preparing local PDF runtime: "
        + str(venv_dir)
        + "\nRequired: "
        + " ".join(REQUIRED_RUNTIME_DEPENDENCIES)
        + "\nOptional preferred renderer: "
        + " ".join(OPTIONAL_RUNTIME_DEPENDENCIES),
        file=sys.stderr,
    )
    subprocess.run(
        [str(py), "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
    )
    install_packages(py, REQUIRED_RUNTIME_DEPENDENCIES, required=True)
    install_packages(py, OPTIONAL_RUNTIME_DEPENDENCIES, required=False)

    run_in_runtime(py, attempt)


def ensure_dependencies():
    try:
        import markdown  # type: ignore
    except ModuleNotFoundError:
        bootstrap_and_reexec("missing required Python package: markdown")

    weasy_error: Exception | None = None
    weasy_stdout = io.StringIO()
    weasy_stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(weasy_stdout), contextlib.redirect_stderr(weasy_stderr):
            from weasyprint import HTML  # type: ignore

        return markdown, "weasyprint", HTML
    except Exception as exc:  # WeasyPrint can fail on native DLL imports.
        weasy_error = exc

    try:
        import reportlab  # type: ignore  # noqa: F401
    except ModuleNotFoundError:
        bootstrap_and_reexec("WeasyPrint unavailable and ReportLab fallback is missing")

    if weasy_error is not None:
        print(
            "Warning: WeasyPrint is unavailable; using ReportLab fallback.\n"
            f"WeasyPrint error: {type(weasy_error).__name__}: {weasy_error}",
            file=sys.stderr,
        )

    return markdown, "reportlab", None


def slugify(value: str, used: set[str]) -> str:
    slug = re.sub(r"<[^>]+>", "", value).strip()
    slug = re.sub(r"[^\w\s\u4e00-\u9fff-]", "-", slug, flags=re.UNICODE)
    slug = re.sub(r"\s+", "-", slug).strip("-").lower() or "section"
    base = slug
    i = 2
    while slug in used:
        slug = f"{base}-{i}"
        i += 1
    used.add(slug)
    return slug


def extract_cover(markdown_text: str, fallback_title: str) -> tuple[str, str, str]:
    lines = markdown_text.splitlines()
    title = fallback_title
    subtitle_lines: list[str] = []
    body_start = 0

    if lines and lines[0].startswith("# "):
        heading_title = lines[0][2:].strip()
        if FRONT_MATTER_HEADING_RE.match(heading_title):
            print(
                "Warning: first H1 looks like front matter, not a document title. "
                "Keep it in body; use '##' for prefaces/introductions and pass "
                "an explicit PDF title.",
                file=sys.stderr,
            )
            body = "\n".join(lines)
            return title, "", body

        title = heading_title or fallback_title
        body_start = 1
        while body_start < len(lines) and lines[body_start].startswith(">"):
            subtitle_lines.append(lines[body_start][1:].strip())
            body_start += 1
        while body_start < len(lines) and lines[body_start].strip() in {"", "---"}:
            body_start += 1

    body = "\n".join(lines[body_start:])
    subtitle_html = "<br/>".join(html.escape(line) for line in subtitle_lines)
    return title, subtitle_html, body


def strip_frontmatter(markdown_text: str) -> str:
    """Drop YAML/TOML frontmatter when a source file includes document metadata."""
    markdown_text = markdown_text.lstrip("\ufeff")
    text = markdown_text.lstrip()
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            after = text.find("\n", end + 4)
            return text[after + 1 :].lstrip() if after != -1 else ""
    if text.startswith("+++\n"):
        end = text.find("\n+++", 4)
        if end != -1:
            after = text.find("\n", end + 4)
            return text[after + 1 :].lstrip() if after != -1 else ""
    return markdown_text


def remove_section_separator_rules(markdown_text: str) -> str:
    """Treat a rule directly before a level-2 heading as a structural separator."""
    return re.sub(
        r"\n{0,2}[ \t]*---[ \t]*\n+(?=##\s+)",
        "\n\n",
        markdown_text,
    )


def clean_heading_text(raw_text: str) -> str:
    return raw_text.strip().rstrip("#").strip()


def print_toc_preview(h2_headings: list[tuple[int, str]]) -> None:
    print("PDF 目录预览：", file=sys.stderr)
    for lineno, text in h2_headings:
        print(f"  - {text}  (line {lineno})", file=sys.stderr)


def validate_markdown_structure(markdown_text: str) -> None:
    markdown_text = markdown_text.lstrip("\ufeff")
    errors: list[str] = []
    headings: list[tuple[int, int, str, str]] = []
    lines = markdown_text.splitlines()

    for lineno, line in enumerate(lines, start=1):
        match = MARKDOWN_HEADING_RE.match(line)
        if not match:
            continue
        level = len(match.group(1))
        heading_text = clean_heading_text(match.group(2))
        headings.append((lineno, level, heading_text, line))

        if FRONT_MATTER_HEADING_RE.match(heading_text) and level != 2:
            errors.append(
                f"第 {lineno} 行：`{line}`。"
                f"`{heading_text}` 是前置内容，应使用二级标题；"
                "只有导论内部的小节才使用三级标题。"
            )

    h1_headings = [heading for heading in headings if heading[1] == 1]
    h2_headings = [(lineno, text) for lineno, level, text, _ in headings if level == 2]

    if not h1_headings:
        errors.append(
            "缺少一级标题。`delivery/final.md` 的第一行应是整本书或课程的名字，"
            "例如 `# 为什么——如何问好问题`。"
        )
    elif len(h1_headings) > 1:
        lines = ", ".join(str(lineno) for lineno, _, _, _ in h1_headings)
        errors.append(
            f"一级标题只能有一个，现在出现在第 {lines} 行。"
            "整本产品标题使用 `#`，章节和讲次使用 `##`。"
        )
    else:
        lineno, _, title, line = h1_headings[0]
        first_content_line = next(
            (
                index
                for index, text in enumerate(markdown_text.splitlines(), start=1)
                if text.strip()
            ),
            lineno,
        )
        if lineno != first_content_line:
            errors.append(
                f"第 {lineno} 行：`{line}`。一级标题需要放在正文第一行，"
                "作为封面标题和 PDF 元数据标题。"
            )
        if GENERIC_DOCUMENT_TITLE_RE.match(title):
            errors.append(
                f"第 {lineno} 行：`{line}`。一级标题要写读者看到的书名或课程名，"
                "不能写后台文件名或生产阶段名称。"
            )
        if FRONT_MATTER_HEADING_RE.match(title):
            errors.append(
                f"第 {lineno} 行：`{line}`。`{title}` 不是整本产品标题，"
                "请把它改成 `## {title}`，并在第一行写书名。"
            )
        subtitle_line_index = lineno
        if subtitle_line_index >= len(lines):
            errors.append(
                "缺少封面副标题。一级标题下一行必须写一行引用格式副标题，"
                "例如 `> 因果科学入门课`。"
            )
        else:
            subtitle_line = lines[subtitle_line_index]
            if not subtitle_line.startswith("> "):
                errors.append(
                    f"第 {subtitle_line_index + 1} 行：`{subtitle_line}`。"
                    "一级标题下一行必须写封面副标题，格式为 `> 副标题`；"
                    "不要用冒号标题或正文段落代替。"
                )
            elif not subtitle_line[2:].strip():
                errors.append(
                    f"第 {subtitle_line_index + 1} 行：`{subtitle_line}`。"
                    "副标题不能为空，请写成 `> 一句能说明这份作品价值的副标题`。"
                )

    if not h2_headings:
        errors.append("没有二级标题，PDF 目录会为空。请用 `##` 标出章节、讲次或前置内容。")

    has_numbered_sections = any(
        NUMBERED_SECTION_RE.match(text) for _, text in h2_headings
    )
    if has_numbered_sections:
        misplaced_headings = [
            (lineno, text)
            for lineno, text in h2_headings
            if not (
                NUMBERED_SECTION_RE.match(text)
                or BOOK_EDGE_HEADING_RE.match(text)
            )
        ]
        if misplaced_headings:
            details = "\n".join(
                f"- 第 {lineno} 行：`## {text}`" for lineno, text in misplaced_headings
            )
            errors.append(
                "这些二级标题会进入 PDF 目录，但当前文档已经有讲次结构，"
                "它们更像讲内小标题。请改成 `###` 或正文加粗：\n"
                + details
            )

    if errors:
        raise MarkdownFormatError(
            "PDF 生成前结构体检没有通过：\n"
            + "\n".join(f"- {error}" for error in errors)
            + "\n请先修 `delivery/final.md`。不要为绕过体检另写第二套 PDF 脚本。"
        )

    print_toc_preview(h2_headings)


def add_heading_ids(html_body: str) -> tuple[str, str]:
    toc_items: list[tuple[str, str]] = []
    used: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        level = match.group(1)
        attrs = match.group(2) or ""
        inner = match.group(3)
        text = re.sub(r"<[^>]+>", "", inner).strip()
        anchor = slugify(text, used)
        cls = " lecture" if level == "2" else ""
        if level == "2":
            toc_items.append((anchor, text))
        return f'<h{level}{attrs} id="{anchor}" class="heading{cls}">{inner}</h{level}>'

    html_body = re.sub(r"<h([23])([^>]*)>(.*?)</h\1>", replace, html_body)

    if not toc_items:
        return "", html_body

    items = "\n".join(
        f'<li><a href="#{anchor}">'
        f'<span class="toc-title">{html.escape(text)}</span>'
        f"</a></li>"
        for anchor, text in toc_items
    )
    toc = f'<nav class="toc"><h2>目录</h2><ol>{items}</ol></nav>'
    return toc, html_body


def split_cover_title_lines(title: str, max_chars: int = 10) -> list[str]:
    clean_title = re.sub(r"\s+", " ", title).strip()
    if not clean_title:
        return []

    lines: list[str] = []
    for part in re.split(r"\s*——\s*", clean_title):
        part = part.strip()
        if not part:
            continue
        lines.extend(split_cover_title_part(part, max_chars))
    return lines or [clean_title]


def split_cover_title_part(part: str, max_chars: int) -> list[str]:
    if len(part) <= max_chars:
        return [part]

    split_at = max(2, min(len(part) - 2, len(part) // 2))
    head = part[:split_at].strip()
    tail = part[split_at:].strip()
    if len(tail) == 1 and len(head) > 2:
        head = part[: split_at - 1].strip()
        tail = part[split_at - 1 :].strip()

    return [head, *split_cover_title_part(tail, max_chars)]


def build_cover_title_html(title: str) -> str:
    clean_title = re.sub(r"\s+", " ", title).strip()
    title_lines = split_cover_title_lines(title, max_chars=12)

    html_lines: list[str] = []
    for index, line in enumerate(part for part in title_lines if part):
        line_class = "cover-title-line"
        if index == 0 and len(line) <= 6 and len(title_lines) > 1:
            line_class += " cover-title-kicker"
        else:
            line_class += " cover-title-main"
        html_lines.append(f'<span class="{line_class}">{html.escape(line)}</span>')

    return "\n".join(html_lines) or html.escape(clean_title)


def build_html(markdown_text: str, title: str, markdown_module) -> str:
    markdown_text = strip_frontmatter(markdown_text)
    validate_markdown_structure(markdown_text)
    cover_title, subtitle_html, body_md = extract_cover(markdown_text, title)
    body_md = remove_section_separator_rules(body_md)
    body_html = markdown_module.markdown(
        body_md,
        extensions=["extra", "tables", "sane_lists"],
        output_format="html5",
    )
    body_html = re.sub(r"<hr\s*/?>\s*<hr\s*/?>", "<hr/>", body_html)
    toc_html, body_html = add_heading_ids(body_html)

    escaped_title = html.escape(cover_title)
    cover_title_html = build_cover_title_html(cover_title)
    subtitle = f'<p class="subtitle">{subtitle_html}</p>' if subtitle_html else ""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{escaped_title}</title>
<style>
@page {{
  size: 108mm 192mm;
  margin: 12mm 10.5mm 14mm 10.5mm;
  background: #fffdf8;
  @bottom-center {{
    content: counter(page);
    color: #9f968a;
    font-size: 7.6pt;
  }}
}}
@page cover {{
  size: 108mm 192mm;
  margin: 15mm 12mm 14mm 12mm;
  background: #fffdf8;
  @bottom-center {{ content: ""; }}
}}
@page toc {{
  size: 108mm 192mm;
  margin: 14mm 12mm 14mm 12mm;
  background: #fffdf8;
  @bottom-center {{
    content: counter(page);
    color: #9f968a;
    font-size: 7.6pt;
  }}
}}
:root {{
  --paper: #fffdf8;
  --ink: #292721;
  --heading: #1f211d;
  --muted: #746d63;
  --hairline: #e9dfd2;
  --accent: #9a6a3a;
  --accent-soft: #d9bd92;
  --wash: #f8f1e7;
  --code: #f3eee6;
}}
* {{ box-sizing: border-box; }}
html {{ background: var(--paper); }}
body {{
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: "Noto Serif CJK SC", "Noto Sans CJK SC", "Source Han Serif SC",
    "Source Han Sans SC", "Songti SC", "PingFang SC", "Microsoft YaHei", serif;
  font-size: 10.85pt;
  line-height: 1.72;
  letter-spacing: 0.004em;
  text-align: left;
  word-break: break-word;
  overflow-wrap: anywhere;
}}
.cover {{
  page: cover;
  min-height: 160mm;
  padding-top: 35mm;
  text-align: left;
  page-break-after: always;
}}
.cover::before {{
  content: "";
  display: block;
  width: 74mm;
  border-top: 1.2px solid var(--accent);
  margin: 0 0 10mm;
}}
.cover h1 {{
  max-width: 81mm;
  margin: 0;
  padding: 0;
  border: 0;
  color: var(--heading);
  font-family: "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC",
    "Microsoft YaHei", sans-serif;
  text-align: left;
}}
.cover-title-line {{
  display: block;
}}
.cover-title-kicker {{
  margin-bottom: 0.08em;
  font-size: 24pt;
  font-weight: 680;
  line-height: 1.12;
  letter-spacing: 0.015em;
}}
.cover-title-main {{
  font-size: 25.5pt;
  font-weight: 720;
  line-height: 1.15;
  letter-spacing: 0.008em;
}}
.subtitle {{
  margin-top: 6mm;
  color: var(--muted);
  max-width: 78mm;
  font-size: 9.5pt;
  line-height: 1.65;
  text-indent: 0;
}}
.toc {{
  page: toc;
  page-break-after: always;
  padding-top: 0.65em;
}}
.toc h2 {{
  border: 0;
  margin: 0 0 1em;
  padding: 0.35em 0 0.55em;
  border-bottom: 1px solid var(--hairline);
  text-align: left;
  page-break-before: avoid;
  font-size: 13.5pt;
}}
.toc ol {{
  list-style: none;
  margin: 0;
  padding: 0;
}}
.toc li {{
  border-bottom: 1px solid var(--hairline);
  margin: 0;
  padding: 0.5em 0;
  text-indent: 0;
}}
.toc a {{
  display: block;
  color: var(--ink);
  text-decoration: none;
}}
.toc-title {{
  display: block;
  font-size: 9.9pt;
  line-height: 1.48;
  letter-spacing: 0.002em;
}}
h1, h2, h3, h4 {{
  color: var(--heading);
  font-family: "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC",
    "Microsoft YaHei", sans-serif;
  font-weight: 650;
  text-align: left;
  page-break-after: avoid;
  break-after: avoid;
}}
h1 {{
  font-size: 19pt;
  line-height: 1.35;
  text-align: center;
}}
h2 {{
  margin: 1.45em 0 0.82em;
  padding-top: 0;
  font-size: 14.75pt;
  line-height: 1.34;
  letter-spacing: 0.012em;
}}
h2::before {{
  content: "";
  display: block;
  width: 17mm;
  border-top: 1.1px solid var(--accent);
  margin: 0 0 0.72em;
}}
h2.lecture {{
  page-break-before: always;
  break-before: page;
}}
main > h2.lecture:first-child {{
  page-break-before: avoid;
  break-before: avoid;
}}
h3 {{
  margin: 1.45em 0 0.48em;
  padding-left: 0;
  border: 0;
  color: #353027;
  font-size: 12.3pt;
  line-height: 1.45;
}}
h4 {{
  margin: 1.05em 0 0.36em;
  color: #4b443a;
  font-size: 10.8pt;
}}
p {{
  margin: 0.62em 0;
  text-indent: 0;
}}
h1 + p, h2 + p, h3 + p, h4 + p, blockquote + p, table + p, hr + p,
.cover + p, .toc + p, li p {{
  text-indent: 0;
}}
blockquote {{
  margin: 1.05em 0;
  padding: 0.76em 0.9em;
  border-left: 2px solid var(--accent-soft);
  background: var(--wash);
  border-radius: 5px;
  break-inside: avoid;
}}
blockquote p {{
  margin: 0.38em 0;
  text-indent: 0;
  color: #4a4339;
}}
ul, ol {{
  margin: 0.86em 0 0.92em 1.08em;
  padding-left: 0;
}}
ul {{ list-style: disc outside; }}
ol {{ list-style: decimal outside; }}
li {{
  margin: 0.3em 0;
  padding-left: 0.08em;
  text-indent: 0;
}}
li > p {{
  margin: 0.25em 0;
  text-indent: 0;
}}
table {{
  width: 100%;
  margin: 1em 0 1.12em;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 8.85pt;
  line-height: 1.46;
  word-break: break-word;
  break-inside: avoid;
}}
th, td {{
  border: 0;
  border-bottom: 1px solid var(--hairline);
  padding: 0.48em 0.42em;
  vertical-align: top;
}}
th {{
  border-top: 1px solid var(--hairline);
  background: var(--wash);
  color: #3b352c;
  font-weight: 650;
}}
code {{
  font-family: "SF Mono", "Noto Sans Mono CJK SC", monospace;
  font-size: 0.9em;
  background: var(--code);
  padding: 0.08em 0.25em;
  border-radius: 3px;
}}
pre {{
  white-space: pre-wrap;
  background: var(--code);
  padding: 0.76em 0.84em;
  border-radius: 5px;
  font-size: 9pt;
  line-height: 1.5;
  break-inside: avoid;
}}
pre code {{
  background: transparent;
  padding: 0;
}}
img {{ max-width: 100%; }}
hr {{
  border: 0;
  border-top: 1px solid var(--hairline);
  width: 34%;
  margin: 1.65em auto;
}}
strong {{
  color: #1f1b16;
  font-weight: 650;
}}
a {{
  color: var(--accent);
  text-decoration: none;
}}
p, li, blockquote, table {{
  orphans: 2;
  widows: 2;
}}
</style>
</head>
<body>
<section class="cover"><h1>{cover_title_html}</h1>{subtitle}</section>
{toc_html}
<main>
{body_html}
</main>
</body>
</html>
"""


def markdown_inline_to_reportlab(text: str, strong_font_name: str | None = None) -> str:
    strong_font_open = '<font color="#1f1b16">'
    if strong_font_name:
        strong_font_open = f'<font name="{html.escape(strong_font_name, quote=True)}" color="#1f1b16">'

    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", strong_font_open + r"\1</font>", text)
    text = re.sub(r"__([^_]+)__", strong_font_open + r"\1</font>", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    return text


def reportlab_section_anchor(index: int) -> str:
    return f"h2-{index:02d}"


def reportlab_toc_link_markup(
    _index: int, heading: str, anchor: str, strong_font_name: str | None = None
) -> str:
    item = markdown_inline_to_reportlab(heading, strong_font_name)
    return f'<link href="#{html.escape(anchor)}">{item}</link>'


def reportlab_heading_anchor_markup(
    heading: str, anchor: str, strong_font_name: str | None = None
) -> str:
    return f'<a name="{html.escape(anchor)}"/>{markdown_inline_to_reportlab(heading, strong_font_name)}'


def reportlab_h2_headings(markdown_text: str) -> list[str]:
    headings: list[str] = []
    for line in markdown_text.splitlines():
        match = MARKDOWN_HEADING_RE.match(line)
        if match and len(match.group(1)) == 2:
            headings.append(clean_heading_text(match.group(2)))
    return headings


def reportlab_font_names(pdfmetrics, UnicodeCIDFont, TTFont) -> tuple[str, str, str]:
    def register_ttf(name: str, candidates: list[str]) -> str | None:
        for candidate in candidates:
            path = Path(candidate)
            if not path.exists():
                continue
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
                return name
            except Exception:
                continue
        return None

    body_name = register_ttf(
        "KBBNotoSerifSC",
        [
            "C:/Windows/Fonts/NotoSerifSC-VF.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
            "/usr/share/fonts/opentype/adobe-source-han-serif/SourceHanSerifSC-Regular.otf",
        ],
    )
    heading_name = register_ttf(
        "KBBHeadingSC",
        [
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/NotoSansSC-VF.ttf",
            "C:/Windows/Fonts/msyh.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/adobe-source-han-sans/SourceHanSansSC-Bold.otf",
        ],
    )
    strong_name = register_ttf(
        "KBBStrongSC",
        [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/NotoSansSC-VF.ttf",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/adobe-source-han-sans/SourceHanSansSC-Bold.otf",
        ],
    )

    if body_name and heading_name and strong_name:
        return body_name, heading_name, strong_name

    fallback_name = "STSong-Light"
    try:
        pdfmetrics.getFont(fallback_name)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(fallback_name))
    return body_name or fallback_name, heading_name or fallback_name, strong_name or heading_name or fallback_name


def build_reportlab_pdf(markdown_text: str, title: str, output_path: Path) -> None:
    from reportlab.lib import colors  # type: ignore
    from reportlab.lib.enums import TA_LEFT  # type: ignore
    from reportlab.lib.pagesizes import portrait  # type: ignore
    from reportlab.lib.styles import ParagraphStyle  # type: ignore
    from reportlab.lib.units import mm  # type: ignore
    from reportlab.pdfbase import pdfmetrics  # type: ignore
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont  # type: ignore
    from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
    from reportlab.platypus import (  # type: ignore
        Flowable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    class Hairline(Flowable):
        def __init__(
            self,
            width: float,
            color,
            *,
            thickness: float = 0.65,
            space_before: float = 0,
            space_after: float = 0,
        ) -> None:
            super().__init__()
            self.requested_width = width
            self.color = color
            self.thickness = thickness
            self.space_before = space_before
            self.space_after = space_after
            self.draw_width = width
            self.draw_height = space_before + thickness + space_after

        def wrap(self, availWidth, availHeight):  # type: ignore[no-untyped-def]
            self.draw_width = min(self.requested_width, availWidth)
            self.draw_height = self.space_before + self.thickness + self.space_after
            return self.draw_width, self.draw_height

        def draw(self) -> None:
            y = self.draw_height - self.space_before - (self.thickness / 2)
            self.canv.saveState()
            self.canv.setStrokeColor(self.color)
            self.canv.setLineWidth(self.thickness)
            self.canv.line(0, y, self.draw_width, y)
            self.canv.restoreState()

    class LinkedTocDocTemplate(SimpleDocTemplate):
        def afterFlowable(self, flowable) -> None:  # type: ignore[no-untyped-def]
            bookmark_name = getattr(flowable, "_bookmark_name", None)
            bookmark_title = getattr(flowable, "_bookmark_title", None)
            if bookmark_name and bookmark_title:
                self.canv.bookmarkPage(bookmark_name)
                self.canv.addOutlineEntry(bookmark_title, bookmark_name, level=0, closed=False)

    markdown_text = strip_frontmatter(markdown_text)
    validate_markdown_structure(markdown_text)
    cover_title, subtitle_html, body_md = extract_cover(markdown_text, title)
    body_md = remove_section_separator_rules(body_md)

    font_name, heading_font_name, strong_font_name = reportlab_font_names(pdfmetrics, UnicodeCIDFont, TTFont)

    page_size = portrait((108 * mm, 192 * mm))
    paper_color = colors.HexColor("#fffdf8")
    ink_color = colors.HexColor("#292721")
    heading_color = colors.HexColor("#1f211d")
    muted_color = colors.HexColor("#746d63")
    hairline_color = colors.HexColor("#e9dfd2")
    accent_color = colors.HexColor("#9a6a3a")
    accent_soft_color = colors.HexColor("#d9bd92")
    wash_color = colors.HexColor("#f8f1e7")
    code_color = colors.HexColor("#f3eee6")

    def inline_markdown(text: str) -> str:
        return markdown_inline_to_reportlab(text, strong_font_name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = LinkedTocDocTemplate(
        str(output_path),
        pagesize=page_size,
        leftMargin=10.5 * mm,
        rightMargin=10.5 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title=cover_title,
        author="knowledge-bread-bakery",
    )

    styles = {
        "cover_title": ParagraphStyle(
            "cover_title",
            fontName=heading_font_name,
            fontSize=23.2,
            leading=27.4,
            textColor=heading_color,
            alignment=TA_LEFT,
            wordWrap="CJK",
            spaceAfter=1,
        ),
        "cover_title_long": ParagraphStyle(
            "cover_title_long",
            fontName=heading_font_name,
            fontSize=21.2,
            leading=25.6,
            textColor=heading_color,
            alignment=TA_LEFT,
            wordWrap="CJK",
            spaceAfter=1,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName=font_name,
            fontSize=9.5,
            leading=16,
            textColor=muted_color,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
        "toc_title": ParagraphStyle(
            "toc_title",
            fontName=heading_font_name,
            fontSize=13.5,
            leading=18.5,
            textColor=heading_color,
            alignment=TA_LEFT,
            wordWrap="CJK",
            spaceAfter=4,
        ),
        "toc_item": ParagraphStyle(
            "toc_item",
            fontName=font_name,
            fontSize=9.9,
            leading=14.7,
            textColor=ink_color,
            alignment=TA_LEFT,
            wordWrap="CJK",
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=3,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=font_name,
            fontSize=10.85,
            leading=18.6,
            textColor=ink_color,
            alignment=TA_LEFT,
            wordWrap="CJK",
            spaceAfter=6.7,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName=heading_font_name,
            fontSize=14.75,
            leading=19.8,
            textColor=heading_color,
            alignment=TA_LEFT,
            wordWrap="CJK",
            spaceBefore=0,
            spaceAfter=10,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "h3",
            fontName=heading_font_name,
            fontSize=12.3,
            leading=17.8,
            textColor=colors.HexColor("#353027"),
            alignment=TA_LEFT,
            wordWrap="CJK",
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "quote": ParagraphStyle(
            "quote",
            fontName=font_name,
            fontSize=10.5,
            leading=17.2,
            textColor=colors.HexColor("#4a4339"),
            backColor=wash_color,
            borderColor=accent_soft_color,
            borderWidth=0.7,
            borderPadding=6,
            leftIndent=2 * mm,
            rightIndent=1 * mm,
            wordWrap="CJK",
            spaceBefore=6,
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName=font_name,
            fontSize=10.85,
            leading=17.8,
            textColor=ink_color,
            leftIndent=6 * mm,
            firstLineIndent=-4 * mm,
            wordWrap="CJK",
            spaceAfter=5,
        ),
        "pre": ParagraphStyle(
            "pre",
            fontName=font_name,
            fontSize=9.1,
            leading=13.8,
            textColor=ink_color,
            backColor=code_color,
            borderPadding=5,
            wordWrap="CJK",
            spaceBefore=5,
            spaceAfter=7,
        ),
    }

    story = []
    story.append(Spacer(1, 34 * mm))
    story.append(
        Hairline(74 * mm, accent_color, thickness=0.85, space_before=0, space_after=10 * mm)
    )
    for line in split_cover_title_lines(cover_title):
        style_name = "cover_title_long" if len(line) > 8 else "cover_title"
        story.append(Paragraph(inline_markdown(line), styles[style_name]))
    if subtitle_html:
        story.append(Spacer(1, 3.8 * mm))
        story.append(Paragraph(subtitle_html, styles["subtitle"]))
    story.append(PageBreak())

    h2_headings = reportlab_h2_headings(body_md)
    toc_items = [
        (index, heading, reportlab_section_anchor(index))
        for index, heading in enumerate(h2_headings, start=1)
    ]
    if toc_items:
        story.append(Paragraph("目录", styles["toc_title"]))
        story.append(
            Hairline(86 * mm, hairline_color, thickness=0.45, space_before=1.2 * mm, space_after=3 * mm)
        )
        for index, heading, anchor in toc_items:
            story.append(Paragraph(reportlab_toc_link_markup(index, heading, anchor, heading_font_name), styles["toc_item"]))
            story.append(
                Hairline(86 * mm, hairline_color, thickness=0.35, space_before=0, space_after=2.5 * mm)
            )
        story.append(PageBreak())

    def flush_paragraph(buffer: list[str]) -> None:
        if not buffer:
            return
        paragraph = " ".join(part.strip() for part in buffer if part.strip())
        if paragraph:
            story.append(Paragraph(inline_markdown(paragraph), styles["body"]))
        buffer.clear()

    def flush_quote(buffer: list[str]) -> None:
        if not buffer:
            return
        quote = "<br/>".join(inline_markdown(part.strip()) for part in buffer if part.strip())
        if quote:
            story.append(Paragraph(quote, styles["quote"]))
        buffer.clear()

    paragraph_buffer: list[str] = []
    quote_buffer: list[str] = []
    seen_body_h2 = False
    h2_index = 0
    for raw_line in body_md.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph(paragraph_buffer)
            flush_quote(quote_buffer)
            continue

        heading_match = MARKDOWN_HEADING_RE.match(stripped)
        if heading_match:
            flush_paragraph(paragraph_buffer)
            flush_quote(quote_buffer)
            level = len(heading_match.group(1))
            heading_text = clean_heading_text(heading_match.group(2))
            if level == 2:
                if seen_body_h2:
                    story.append(PageBreak())
                seen_body_h2 = True
                h2_index += 1
                anchor = reportlab_section_anchor(h2_index)
                story.append(
                    Hairline(17 * mm, accent_color, thickness=0.75, space_before=0, space_after=7)
                )
                heading = Paragraph(reportlab_heading_anchor_markup(heading_text, anchor, heading_font_name), styles["h2"])
                heading._bookmark_name = anchor  # type: ignore[attr-defined]
                heading._bookmark_title = heading_text  # type: ignore[attr-defined]
                story.append(heading)
            elif level >= 3:
                story.append(Paragraph(inline_markdown(heading_text), styles["h3"]))
            continue

        if stripped in {"---", "***", "___"}:
            flush_paragraph(paragraph_buffer)
            flush_quote(quote_buffer)
            story.append(Hairline(30 * mm, hairline_color, thickness=0.35, space_before=8, space_after=8))
            continue

        if stripped.startswith(">"):
            flush_paragraph(paragraph_buffer)
            quote = stripped.lstrip(">").strip()
            if quote:
                quote_buffer.append(quote)
            continue

        bullet_match = re.match(r"^([-*+])\s+(.+)$", stripped)
        numbered_match = re.match(r"^(\d+)[.)、]\s+(.+)$", stripped)
        if bullet_match:
            flush_paragraph(paragraph_buffer)
            flush_quote(quote_buffer)
            story.append(
                Paragraph(
                    "• " + inline_markdown(bullet_match.group(2)),
                    styles["bullet"],
                )
            )
            continue
        if numbered_match:
            flush_paragraph(paragraph_buffer)
            flush_quote(quote_buffer)
            story.append(
                Paragraph(
                    f"{numbered_match.group(1)}. " + inline_markdown(numbered_match.group(2)),
                    styles["bullet"],
                )
            )
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph(paragraph_buffer)
            flush_quote(quote_buffer)
            table_line = stripped.strip("|").replace("|", " / ")
            story.append(Paragraph(inline_markdown(table_line), styles["pre"]))
            continue

        flush_quote(quote_buffer)
        paragraph_buffer.append(stripped)

    flush_paragraph(paragraph_buffer)
    flush_quote(quote_buffer)

    def on_page(canvas, document) -> None:  # type: ignore[no-untyped-def]
        canvas.saveState()
        canvas.setFillColor(paper_color)
        canvas.rect(0, 0, page_size[0], page_size[1], fill=1, stroke=0)
        if canvas.getPageNumber() > 1:
            canvas.setFillColor(muted_color)
            canvas.setFont("Helvetica", 7.6)
            canvas.drawCentredString(page_size[0] / 2, 6.2 * mm, str(canvas.getPageNumber()))
        canvas.restoreState()
        canvas.setTitle(cover_title)
        canvas.setAuthor("knowledge-bread-bakery")

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print("Usage: python scripts/build-mobile-pdf.py input.md output.pdf [title]")
        return 0

    if len(sys.argv) < 3:
        print("Usage: python scripts/build-mobile-pdf.py input.md output.pdf [title]", file=sys.stderr)
        return 2

    markdown_module, renderer_name, html_renderer = ensure_dependencies()

    input_path = Path(sys.argv[1]).expanduser().resolve()
    output_path = Path(sys.argv[2]).expanduser().resolve()
    title = sys.argv[3] if len(sys.argv) > 3 else input_path.stem

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    markdown_text = input_path.read_text(encoding="utf-8-sig")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if renderer_name == "weasyprint":
            html_text = build_html(markdown_text, title, markdown_module)
            html_renderer(string=html_text, base_url=str(input_path.parent)).write_pdf(str(output_path))
        else:
            build_reportlab_pdf(markdown_text, title, output_path)
    except MarkdownFormatError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"PDF generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
