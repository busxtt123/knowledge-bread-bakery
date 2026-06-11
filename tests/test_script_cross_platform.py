from __future__ import annotations

import importlib.util
import os
import sys
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


class RuntimePathCrossPlatformTests(unittest.TestCase):
    def test_pdf_runtime_uses_short_windows_path(self) -> None:
        pdf = load_script("build_mobile_pdf_cross_platform", "scripts/build-mobile-pdf.py")
        with (
            patch.object(pdf.os, "name", "nt"),
            patch.dict(os.environ, {"LOCALAPPDATA": "C:/Users/example/AppData/Local"}, clear=True),
        ):
            runtime = pdf.runtime_dir()
            python_path = pdf.runtime_python()

        self.assertEqual(runtime, Path("C:/Users/example/AppData/Local") / "knowledge-bread-bakery" / f"pdf-venv-py{sys.version_info.major}{sys.version_info.minor}")
        self.assertEqual(python_path.name, "python.exe")
        self.assertEqual(python_path.parent.name, "Scripts")

    def test_pdf_runtime_uses_skill_local_posix_path(self) -> None:
        pdf = load_script("build_mobile_pdf_cross_platform_posix", "scripts/build-mobile-pdf.py")
        with (
            patch.object(pdf.os, "name", "posix"),
            patch.object(pdf, "skill_root", return_value=SKILL_DIR),
            patch.dict(os.environ, {}, clear=True),
        ):
            runtime = pdf.runtime_dir()
            python_path = pdf.runtime_python()

        self.assertEqual(runtime, SKILL_DIR / ".skill-runtime" / "pdf-venv")
        self.assertEqual(python_path, runtime / "bin" / "python")

    def test_convert_runtime_uses_platform_specific_python_paths(self) -> None:
        convert = load_script("convert_source_cross_platform", "scripts/convert-source-to-md.py")
        with (
            patch.object(convert.os, "name", "nt"),
            patch.dict(os.environ, {"LOCALAPPDATA": "C:/Users/example/AppData/Local"}, clear=True),
        ):
            self.assertEqual(convert.runtime_python().parent.name, "Scripts")

        with (
            patch.object(convert.os, "name", "posix"),
            patch.object(convert, "skill_root", return_value=SKILL_DIR),
            patch.dict(os.environ, {}, clear=True),
        ):
            self.assertEqual(convert.runtime_python(), convert.runtime_dir() / "bin" / "python")


class OcrDependencyPlanCrossPlatformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.setup = load_script("setup_ocr_deps_cross_platform", "scripts/setup-ocr-deps.py")

    def test_detects_macos_homebrew_plan(self) -> None:
        with (
            patch.object(self.setup.platform, "system", return_value="Darwin"),
            patch.object(self.setup, "command_exists", side_effect=lambda command: command == "brew"),
        ):
            plan = self.setup.detect_install_plan()

        self.assertIsNotNone(plan)
        self.assertEqual(plan.manager, "Homebrew")
        self.assertEqual(plan.commands[0], ["brew", "install", "poppler", "tesseract", "tesseract-lang"])

    def test_detects_linux_apt_plan(self) -> None:
        with (
            patch.object(self.setup.platform, "system", return_value="Linux"),
            patch.object(self.setup, "sudo_prefix", return_value=["sudo"]),
            patch.object(self.setup, "command_exists", side_effect=lambda command: command == "apt-get"),
        ):
            plan = self.setup.detect_install_plan()

        self.assertIsNotNone(plan)
        self.assertEqual(plan.manager, "apt-get")
        self.assertIn(["sudo", "apt-get", "update"], plan.commands)
        self.assertIn("tesseract-ocr-chi-sim", plan.commands[1])

    def test_detects_windows_winget_plan(self) -> None:
        with (
            patch.object(self.setup.platform, "system", return_value="Windows"),
            patch.object(self.setup, "command_exists", side_effect=lambda command: command == "winget"),
        ):
            plan = self.setup.detect_install_plan()

        self.assertIsNotNone(plan)
        self.assertEqual(plan.manager, "winget")
        self.assertTrue(any("UB-Mannheim.TesseractOCR" in command for command in plan.commands))
        self.assertTrue(any("oschwartz10612.Poppler" in command for command in plan.commands))


class OcrCommandCrossPlatformTests(unittest.TestCase):
    def test_cmd_wrapping_only_applies_to_windows_batch_files(self) -> None:
        ocr = load_script("ocr_pdf_to_md_cross_platform", "scripts/ocr-pdf-to-md.py")
        with (
            patch.object(ocr.os, "name", "nt"),
            patch.object(ocr, "command_path", return_value="C:/Tools/example.cmd"),
        ):
            self.assertEqual(
                ocr.command_args("example", "--version"),
                ["cmd.exe", "/d", "/c", "C:/Tools/example.cmd", "--version"],
            )

        with (
            patch.object(ocr.os, "name", "posix"),
            patch.object(ocr, "command_path", return_value="/usr/bin/example"),
        ):
            self.assertEqual(ocr.command_args("example", "--version"), ["/usr/bin/example", "--version"])


if __name__ == "__main__":
    unittest.main()
