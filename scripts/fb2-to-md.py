#!/usr/bin/env python3
"""Convert FB2 (FictionBook) XML to clean Markdown."""

import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"fb": "http://www.gribuser.ru/xml/fictionbook/2.0"}

def text_of(elem) -> str:
    """Get all text content from an element, stripping inline tags."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "emphasis":
            inner = text_of(child).strip()
            if inner:
                parts.append(f"*{inner}*")
        elif tag == "strong":
            inner = text_of(child).strip()
            if inner:
                parts.append(f"**{inner}**")
        elif tag == "empty-line":
            parts.append("\n")
        elif tag in ("p", "title", "subtitle", "epigraph", "text-author", "poem", "stanza", "v", "cite", "code"):
            parts.append(text_of(child))
        elif tag == "image":
            pass  # skip images in text
        elif tag == "a":
            href = child.attrib.get("{http://www.w3.org/1999/xlink}href", "")
            inner = text_of(child).strip()
            if inner and href:
                parts.append(f"[{inner}]({href})")
            elif inner:
                parts.append(inner)
        else:
            ct = text_of(child)
            if ct:
                parts.append(ct)
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def convert_section(section, depth: int = 1) -> list[str]:
    """Convert an FB2 section to Markdown lines."""
    lines = []
    title_elem = section.find("fb:title", NS)
    if title_elem is not None:
        title_text = text_of(title_elem).strip()
        if title_text:
            lines.append(f"{'#' * min(depth, 6)} {title_text}")
            lines.append("")

    for child in section:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "title":
            continue  # already handled

        elif tag == "p":
            t = text_of(child).strip()
            if t:
                # Handle special formatting at paragraph level
                lines.append(t)
                lines.append("")

        elif tag == "subtitle":
            t = text_of(child).strip()
            if t:
                lines.append(f"**{t}**")
                lines.append("")

        elif tag == "empty-line":
            lines.append("")

        elif tag == "epigraph":
            inner = text_of(child).strip()
            if inner:
                lines.append(f"> {inner}")
                lines.append("")

        elif tag == "poem":
            stanzas = child.findall("fb:stanza", NS)
            if stanzas:
                for stanza in stanzas:
                    for v in stanza.findall("fb:v", NS):
                        vtext = text_of(v).strip()
                        if vtext:
                            lines.append(f"  {vtext}")
                    lines.append("")
            else:
                # direct verse lines
                for v in child.findall("fb:v", NS):
                    vtext = text_of(v).strip()
                    if vtext:
                        lines.append(f"  {vtext}")
                lines.append("")

        elif tag == "cite":
            inner = text_of(child).strip()
            if inner:
                lines.append(f"> {inner}")
                lines.append("")

        elif tag == "code":
            inner = text_of(child).strip()
            if inner:
                lines.append(f"`{inner}`")

        elif tag == "text-author":
            t = text_of(child).strip()
            if t:
                lines.append(f"  — {t}")
                lines.append("")

        elif tag == "section":
            lines.extend(convert_section(child, depth + 1))

    return lines


def convert_fb2(source: Path) -> str:
    raw_text = read_fb2_safe(source)
    root = ET.fromstring(raw_text)

    parts = []

    # Title info from description
    desc = root.find(".//fb:description", NS)
    if desc is not None:
        title_info = desc.find("fb:title-info", NS)
        if title_info is not None:
            book_title = title_info.find("fb:book-title", NS)
            author = title_info.find("fb:author", NS)
            annotation = title_info.find("fb:annotation", NS)

            if author is not None:
                fn = author.find("fb:first-name", NS)
                ln = author.find("fb:last-name", NS)
                author_name = ""
                if fn is not None:
                    author_name += (fn.text or "").strip() + " "
                if ln is not None:
                    author_name += (ln.text or "").strip()
                if author_name.strip():
                    parts.append(f"# {book_title.text.strip() if book_title is not None and book_title.text else ''}")
                    parts.append("")
                    parts.append(f"**作者：{author_name.strip()}**")
                    parts.append("")

            if annotation is not None:
                anno_text = text_of(annotation).strip()
                if anno_text:
                    parts.append(anno_text)
                    parts.append("")

    # Convert body content
    body = root.find("fb:body", NS)
    if body is None:
        # Try without namespace
        body = root.find("body")

    if body is not None:
        # Process sections
        sections = body.findall("fb:section", NS) if NS else body.findall("section")
        for section in sections:
            parts.extend(convert_section(section))
            parts.append("---")
            parts.append("")

    return "\n".join(parts).strip()


def read_fb2_safe(path: Path) -> str:
    """Read FB2 file, handling common CP-1252-as-UTF-8 encoding bugs."""
    raw = path.read_bytes()
    # Try UTF-8 first
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    # Some FB2 files declare UTF-8 but contain CP-1252-encoded smart quotes
    # and dashes in the range 0x80-0x9F. Fix them at the byte level.
    cp1252_fixes = {
        0x80: "€",  # €
        0x82: "‚",  # ‚
        0x83: "ƒ",  # ƒ
        0x84: "„",  # „
        0x85: "…",  # …
        0x86: "†",  # †
        0x87: "‡",  # ‡
        0x88: "ˆ",  # ˆ
        0x89: "‰",  # ‰
        0x8A: "Š",  # Š
        0x8B: "‹",  # ‹
        0x8C: "Œ",  # Œ
        0x8E: "Ž",  # Ž
        0x91: "‘",  # '
        0x92: "’",  # '
        0x93: "“",  # "
        0x94: "”",  # "
        0x95: "•",  # •
        0x96: "–",  # –
        0x97: "—",  # —
        0x98: "˜",  # ˜
        0x99: "™",  # ™
        0x9A: "š",  # š
        0x9B: "›",  # ›
        0x9C: "œ",  # œ
        0x9E: "ž",  # ž
        0x9F: "Ÿ",  # Ÿ
    }
    result = bytearray()
    for b in raw:
        if b in cp1252_fixes:
            result.extend(cp1252_fixes[b].encode("utf-8"))
        else:
            result.append(b)
    return result.decode("utf-8", errors="replace")


def clean_text(text: str) -> str:
    """Clean up common encoding issues and normalize whitespace."""
    # Normalize common problematic characters to ASCII equivalents
    # where the FB2 uses fancy typographic characters
    text = text.replace("‘", "'").replace("’", "'")  # smart single quotes
    text = text.replace("“", '"').replace("”", '"')  # smart double quotes
    text = text.replace("–", "—").replace("—", "—")  # dashes to em-dash
    text = text.replace("…", "...")                        # ellipsis
    text = text.replace("•", "•")                          # bullet
    text = text.replace(" ", " ")                          # non-breaking space

    # Multiple newlines to double newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove trailing --- at end
    text = re.sub(r"\n---\s*\n*$", "", text)

    return text.strip() + "\n"


def main():
    if len(sys.argv) != 3:
        print("Usage: python fb2-to-md.py SOURCE.fb2 OUTPUT.md", file=sys.stderr)
        return 1

    source = Path(sys.argv[1]).expanduser().resolve()
    output = Path(sys.argv[2]).expanduser().resolve()

    if not source.exists():
        print(f"Source not found: {source}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)

    text = convert_fb2(source)
    text = clean_text(text)
    output.write_text(text, encoding="utf-8")

    print(f"Markdown generated: {output}")
    print(f"Total characters: {len(text)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
