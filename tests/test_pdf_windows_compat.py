from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_DIR = Path(__file__).resolve().parents[1]


def load_script(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, SKILL_DIR / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script: {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class BuildMobilePdfWindowsCompatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pdf = load_script("build_mobile_pdf_under_test", "scripts/build-mobile-pdf.py")

    def test_configure_stdio_forces_utf8_diagnostics(self) -> None:
        stream_bytes = io.BytesIO()
        fake_stderr = io.TextIOWrapper(stream_bytes, encoding="gbk", errors="replace")

        with patch.object(self.pdf.sys, "stderr", fake_stderr):
            self.pdf.configure_stdio()
            print("PDF 生成前结构体检没有通过：缺少一级标题。", file=self.pdf.sys.stderr)
            self.pdf.sys.stderr.flush()

        decoded = stream_bytes.getvalue().decode("utf-8").replace("\r\n", "\n")
        self.assertEqual(decoded, "PDF 生成前结构体检没有通过：缺少一级标题。\n")

    def test_main_emits_markdown_format_errors_as_utf8(self) -> None:
        stream_bytes = io.BytesIO()
        fake_stderr = io.TextIOWrapper(stream_bytes, encoding="gbk", errors="replace")

        with tempfile.TemporaryDirectory() as tmp:
            input_md = Path(tmp) / "final.md"
            output_pdf = Path(tmp) / "out.pdf"
            input_md.write_text("没有一级标题\n\n## 第一讲\n正文\n", encoding="utf-8")

            with patch.object(sys, "stderr", fake_stderr):
                pdf = load_script("build_mobile_pdf_cli_under_test", "scripts/build-mobile-pdf.py")
                with (
                    patch.object(pdf, "ensure_dependencies", return_value=(object(), "weasyprint", object())),
                    patch.object(pdf.sys, "argv", ["build-mobile-pdf.py", str(input_md), str(output_pdf)]),
                ):
                    exit_code = pdf.main()
                pdf.sys.stderr.flush()

        self.assertEqual(exit_code, 2)
        decoded = stream_bytes.getvalue().decode("utf-8").replace("\r\n", "\n")
        self.assertIn("PDF 生成前结构体检没有通过", decoded)
        self.assertIn("缺少一级标题", decoded)
        self.assertNotIn("PDF ��¯ǰ", decoded)

    def test_cover_title_splits_balanced_chinese_dash_title(self) -> None:
        lines = self.pdf.split_cover_title_lines("工程师知道什么——以及他们是如何知道的")

        self.assertEqual(lines, ["工程师知道什么", "以及他们是如何知道的"])
        self.assertTrue(all(len(line) > 1 for line in lines))
        self.assertNotIn("——", "".join(lines))

    def test_front_matter_headings_accept_colon_subtitles(self) -> None:
        markdown = "\n".join(
            [
                "# 重新理解控制论",
                "> 一门关于反馈、行动和现实约束的课",
                "",
                "## 发刊词：为什么这个问题值得追下去",
                "正文",
                "",
                "## 导论：出发前，先带上这张地图",
                "正文",
                "",
                "## 第 1 讲：反馈从哪里开始",
                "正文",
            ]
        )

        with patch.object(self.pdf, "print_toc_preview"):
            self.pdf.validate_markdown_structure(markdown)

    def test_markdown_structure_accepts_utf8_bom_before_title(self) -> None:
        markdown = "\ufeff# 重新理解控制论\n> 副标题\n\n## 发刊词：为什么这个问题值得追下去\n正文\n"

        with patch.object(self.pdf, "print_toc_preview"):
            self.pdf.validate_markdown_structure(markdown)

    def test_cover_title_splits_long_plain_title_without_orphan(self) -> None:
        lines = self.pdf.split_cover_title_lines("一门关于工程知识如何生长的长课程")

        self.assertGreaterEqual(len(lines), 2)
        self.assertTrue(all(len(line) > 1 for line in lines))

    def test_reportlab_toc_item_links_to_heading_anchor(self) -> None:
        markup = self.pdf.reportlab_toc_link_markup(3, "第1讲：你不知道，但你仍然要决定", "h2-03")

        self.assertIn('<link href="#h2-03">', markup)
        self.assertNotIn("03.", markup)
        self.assertIn("第1讲：你不知道", markup)

    def test_reportlab_inline_markdown_renders_strong_with_font(self) -> None:
        markup = self.pdf.markdown_inline_to_reportlab("这是**关键判断**。", "KBBHeadingSC")

        self.assertIn('<font name="KBBHeadingSC" color="#1f1b16">关键判断</font>', markup)
        self.assertNotIn("**", markup)

    def test_reportlab_heading_markup_defines_matching_anchor(self) -> None:
        markup = self.pdf.reportlab_heading_anchor_markup("第1讲：你不知道，但你仍然要决定", "h2-03")

        self.assertTrue(markup.startswith('<a name="h2-03"/>'))
        self.assertIn("第1讲：你不知道", markup)


if __name__ == "__main__":
    unittest.main()
