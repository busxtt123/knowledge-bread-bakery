#!/usr/bin/env python3
"""
Build a mobile-friendly PDF from Markdown.

Usage:
    python scripts/build-mobile-pdf.py input.md output.pdf [title]

The script keeps the PDF toolchain inside the directory that owns scripts/.
If the current Python cannot import the required packages, it creates
.skill-runtime/pdf-venv there, installs the Python dependencies, and re-runs
itself. No second PDF path is used.
"""

from __future__ import annotations

import html
import os
import re
import subprocess
import sys
import venv
from pathlib import Path


DEPENDENCIES = ("markdown", "weasyprint")
BOOTSTRAP_ENV = "KBM_PDF_BOOTSTRAPPED"
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


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def runtime_python() -> Path:
    root = skill_root() / ".skill-runtime" / "pdf-venv"
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def missing_dependencies() -> list[str]:
    missing: list[str] = []
    for package in DEPENDENCIES:
        try:
            __import__(package)
        except ModuleNotFoundError:
            missing.append(package)
    return missing


def bootstrap_and_reexec(missing: list[str]) -> None:
    if os.environ.get(BOOTSTRAP_ENV) == "1":
        raise SystemExit(
            "PDF dependencies are still missing after bootstrap: "
            + ", ".join(missing)
            + "\nInstall manually in the local runtime:\n"
            + f"  {runtime_python()} -m pip install {' '.join(DEPENDENCIES)}"
        )

    py = runtime_python()
    venv_dir = py.parents[1]
    if not py.exists():
        print(f"Creating local PDF runtime: {venv_dir}", file=sys.stderr)
        venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
    else:
        probe = "; ".join(f"import {package}" for package in DEPENDENCIES)
        result = subprocess.run([str(py), "-c", probe], capture_output=True)
        if result.returncode == 0:
            env = os.environ.copy()
            env[BOOTSTRAP_ENV] = "1"
            os.execvpe(str(py), [str(py), __file__, *sys.argv[1:]], env)

    print(
        "Installing local PDF dependencies inside the skill runtime: "
        + " ".join(DEPENDENCIES),
        file=sys.stderr,
    )
    subprocess.run(
        [str(py), "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
    )
    subprocess.run(
        [str(py), "-m", "pip", "install", *DEPENDENCIES],
        check=True,
    )

    env = os.environ.copy()
    env[BOOTSTRAP_ENV] = "1"
    os.execvpe(str(py), [str(py), __file__, *sys.argv[1:]], env)


def ensure_dependencies():
    missing = missing_dependencies()
    if missing:
        bootstrap_and_reexec(missing)

    import markdown  # type: ignore
    from weasyprint import HTML  # type: ignore

    return markdown, HTML


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
    for index, (lineno, text) in enumerate(h2_headings, start=1):
        print(f"  {index:02d}. {text}  (line {lineno})", file=sys.stderr)


def validate_markdown_structure(markdown_text: str) -> None:
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
                f"`{heading_text}` 是正文入口，应使用二级标题；"
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
        errors.append("没有二级标题，PDF 目录会为空。请用 `##` 标出章节、讲次或正文入口。")

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
            "PDF 出炉前结构体检没有通过：\n"
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
        f'<span class="toc-number">{index:02d}</span>'
        f'<span class="toc-title">{html.escape(text)}</span>'
        f"</a></li>"
        for index, (anchor, text) in enumerate(toc_items, start=1)
    )
    toc = f'<nav class="toc"><h2>目录</h2><ol>{items}</ol></nav>'
    return toc, html_body


def build_cover_title_html(title: str) -> str:
    clean_title = re.sub(r"\s+", " ", title).strip()

    if "——" in clean_title:
        title_lines = [part.strip() for part in clean_title.split("——", 1)]
    else:
        title_lines = [clean_title]

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
    color: #c8beb1;
    font-size: 7pt;
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
  @bottom-center {{ content: ""; }}
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
  font-size: 10.45pt;
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
  counter-reset: toc;
}}
.toc li {{
  border-bottom: 1px solid var(--hairline);
  margin: 0;
  padding: 0.43em 0;
  text-indent: 0;
}}
.toc a {{
  display: grid;
  grid-template-columns: 7.2mm 1fr;
  column-gap: 4.2mm;
  align-items: start;
  color: var(--ink);
  text-decoration: none;
}}
.toc-number {{
  color: var(--muted);
  font-family: "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC",
    "Microsoft YaHei", sans-serif;
  font-size: 7.4pt;
  line-height: 1.58;
  letter-spacing: 0.06em;
}}
.toc-title {{
  display: block;
  font-size: 9.35pt;
  line-height: 1.38;
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
  font-size: 14.6pt;
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
  font-size: 12.1pt;
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
  margin: 0.78em 0 0.78em 1.18em;
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
  font-size: 8.35pt;
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
  font-size: 8.55pt;
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


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print("Usage: python scripts/build-mobile-pdf.py input.md output.pdf [title]")
        return 0

    if len(sys.argv) < 3:
        print("Usage: python scripts/build-mobile-pdf.py input.md output.pdf [title]", file=sys.stderr)
        return 2

    markdown_module, html_renderer = ensure_dependencies()

    input_path = Path(sys.argv[1]).expanduser().resolve()
    output_path = Path(sys.argv[2]).expanduser().resolve()
    title = sys.argv[3] if len(sys.argv) > 3 else input_path.stem

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    markdown_text = input_path.read_text(encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        html_text = build_html(markdown_text, title, markdown_module)
    except MarkdownFormatError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    html_renderer(string=html_text, base_url=str(input_path.parent)).write_pdf(str(output_path))
    print(f"PDF generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
