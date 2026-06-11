from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
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


class OcrPdfWindowsCompatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ocr = load_script("ocr_pdf_to_md_under_test", "scripts/ocr-pdf-to-md.py")

    def test_tesseract_stdout_is_decoded_as_utf8_bytes(self) -> None:
        original_text = (
            "工程师知道什么以及他们是如何知道的。"
            "AI时代这种知识有真正的现场。\n"
            * 12
        )
        mojibake_text = original_text.encode("utf-8").decode("gbk", errors="replace")

        def fake_run(command, *args, **kwargs):
            executable = Path(command[0]).name.lower()
            if executable.startswith("pdftoppm"):
                Path(str(command[-1]) + "-1.png").write_bytes(b"fake image")
                return types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
            if executable.startswith("tesseract"):
                if kwargs.get("text"):
                    return types.SimpleNamespace(returncode=0, stdout=mojibake_text, stderr="")
                return types.SimpleNamespace(
                    returncode=0,
                    stdout=original_text.encode("utf-8"),
                    stderr=b"",
                )
            raise AssertionError(f"Unexpected command: {command}")

        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "input.pdf"
            pdf.write_bytes(b"%PDF-1.7\n")
            with (
                patch.object(self.ocr, "require_ocr_dependencies", return_value=None),
                patch.object(self.ocr.subprocess, "run", side_effect=fake_run),
            ):
                markdown = self.ocr.ocr_pdf(pdf, "chi_sim+eng", 220, None, None)

        self.assertIn("工程师知道什么以及他们是如何知道的", markdown)
        self.assertNotIn("宸ョ▼", markdown)

    def test_windows_path_setup_does_not_use_partial_local_tessdata_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_app_data = Path(tmp) / "LocalAppData"
            partial_tessdata = local_app_data / "knowledge-bread-bakery" / "tessdata"
            partial_tessdata.mkdir(parents=True)
            (partial_tessdata / "chi_sim.traineddata").write_bytes(b"fake")

            with (
                patch.dict(
                    os.environ,
                    {
                        "LOCALAPPDATA": str(local_app_data),
                        "PATH": "",
                        "USERPROFILE": str(Path(tmp) / "UserProfile"),
                    },
                    clear=True,
                ),
                patch.object(self.ocr.os, "name", "nt"),
            ):
                self.ocr.add_windows_ocr_paths()
                self.assertNotIn("TESSDATA_PREFIX", os.environ)


class SetupOcrDepsWindowsCompatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.setup = load_script("setup_ocr_deps_under_test", "scripts/setup-ocr-deps.py")

    def test_windows_tessdata_cache_downloads_all_requested_languages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tessdata = Path(tmp) / "tessdata"
            downloaded: list[str] = []

            def fake_urlretrieve(url, target):
                downloaded.append(Path(target).name)
                Path(target).write_bytes(b"traineddata")
                return str(target), None

            old_tessdata_prefix = os.environ.pop("TESSDATA_PREFIX", None)
            try:
                with (
                    patch.object(self.setup.os, "name", "nt"),
                    patch.object(self.setup, "command_exists", return_value=True),
                    patch.object(self.setup, "tesseract_languages", return_value={"eng"}),
                    patch.object(self.setup, "local_tessdata_dir", return_value=tessdata),
                    patch.object(self.setup.urllib.request, "urlretrieve", side_effect=fake_urlretrieve),
                ):
                    self.setup.install_windows_tessdata("chi_sim+eng")

                self.assertEqual(os.environ.get("TESSDATA_PREFIX"), str(tessdata))
                self.assertTrue((tessdata / "chi_sim.traineddata").exists())
                self.assertTrue((tessdata / "eng.traineddata").exists())
                self.assertEqual(sorted(downloaded), ["chi_sim.traineddata", "eng.traineddata"])
            finally:
                if old_tessdata_prefix is None:
                    os.environ.pop("TESSDATA_PREFIX", None)
                else:
                    os.environ["TESSDATA_PREFIX"] = old_tessdata_prefix


if __name__ == "__main__":
    unittest.main()
