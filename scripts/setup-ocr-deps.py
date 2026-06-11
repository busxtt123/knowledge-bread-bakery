#!/usr/bin/env python3
"""
Check or install system OCR dependencies for scanned PDF fallback.

This script does not run OCR. It prepares the two system tools that
scripts/ocr-pdf-to-md.py needs:

- pdftoppm from Poppler, for rendering PDF pages to images
- tesseract with language data, for recognizing text from images
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InstallPlan:
    manager: str
    commands: list[list[str]]
    note: str = ""


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


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run(command: list[str]) -> int:
    print("+ " + " ".join(command))
    return subprocess.run(command).returncode


def sudo_prefix() -> list[str]:
    if os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() != 0:
        if command_exists("sudo"):
            return ["sudo"]
    return []


def detect_install_plan() -> InstallPlan | None:
    system = platform.system().lower()

    if system == "darwin" and command_exists("brew"):
        return InstallPlan(
            "Homebrew",
            [["brew", "install", "poppler", "tesseract", "tesseract-lang"]],
        )

    if system == "linux":
        prefix = sudo_prefix()
        if command_exists("apt-get"):
            return InstallPlan(
                "apt-get",
                [
                    [*prefix, "apt-get", "update"],
                    [
                        *prefix,
                        "apt-get",
                        "install",
                        "-y",
                        "poppler-utils",
                        "tesseract-ocr",
                        "tesseract-ocr-chi-sim",
                    ],
                ],
            )
        if command_exists("dnf"):
            return InstallPlan(
                "dnf",
                [
                    [
                        *prefix,
                        "dnf",
                        "install",
                        "-y",
                        "poppler-utils",
                        "tesseract",
                        "tesseract-langpack-chi_sim",
                    ]
                ],
            )
        if command_exists("pacman"):
            return InstallPlan(
                "pacman",
                [[*prefix, "pacman", "-Sy", "--needed", "poppler", "tesseract", "tesseract-data-chi_sim"]],
            )

    if system == "windows":
        if command_exists("winget"):
            return InstallPlan(
                "winget",
                [
                    ["winget", "install", "--id", "UB-Mannheim.TesseractOCR", "-e"],
                    ["winget", "install", "--id", "oschwartz10612.Poppler", "-e"],
                ],
                "After installation, restart the terminal so PATH changes take effect.",
            )
        if command_exists("choco"):
            return InstallPlan(
                "Chocolatey",
                [["choco", "install", "tesseract", "poppler", "-y"]],
                "After installation, restart the terminal so PATH changes take effect.",
            )

    return None


def tesseract_languages() -> set[str]:
    if not command_exists("tesseract"):
        return set()
    result = subprocess.run(
        ["tesseract", "--list-langs"],
        capture_output=True,
    )
    if result.returncode != 0:
        return set()

    langs: set[str] = set()
    for line in decode_process_output(result.stdout).splitlines():
        stripped = line.strip()
        if stripped and not stripped.lower().startswith("list of available languages"):
            langs.add(stripped)
    return langs


def install_windows_tessdata(lang: str) -> None:
    if os.name != "nt" or not command_exists("tesseract"):
        return

    requested = requested_languages(lang)
    if not requested:
        return

    tessdata = local_tessdata_dir()
    if tessdata is None:
        return

    default_missing = requested - tesseract_languages()
    if not default_missing:
        return

    tessdata.mkdir(parents=True, exist_ok=True)
    os.environ["TESSDATA_PREFIX"] = str(tessdata)

    for language in sorted(requested):
        target = tessdata / f"{language}.traineddata"
        if target.exists() and target.stat().st_size > 0:
            continue
        url = f"https://github.com/tesseract-ocr/tessdata_fast/raw/main/{language}.traineddata"
        print(f"Downloading Tesseract language data: {language}")
        try:
            urllib.request.urlretrieve(url, target)
        except Exception as exc:
            if target.exists():
                target.unlink()
            raise RuntimeError(
                f"Failed to download Tesseract language data `{language}` from {url}: {exc}"
            ) from exc


def check(lang: str) -> list[str]:
    problems: list[str] = []
    if not command_exists("pdftoppm"):
        problems.append("pdftoppm is missing")
    if not command_exists("tesseract"):
        problems.append("tesseract is missing")
    else:
        configure_windows_tessdata_prefix(lang)
        requested = requested_languages(lang)
        available = tesseract_languages()
        missing = sorted(requested - available)
        if missing:
            problems.append("Tesseract language data is missing: " + ", ".join(missing))
    return problems


def print_plan(plan: InstallPlan | None) -> None:
    if plan is None:
        print(
            "No supported package manager was detected.\n"
            "Install Poppler and Tesseract manually, then make sure `pdftoppm` "
            "and `tesseract` are available on PATH.",
            file=sys.stderr,
        )
        return

    print(f"Detected package manager: {plan.manager}")
    print("Suggested install commands:")
    for command in plan.commands:
        print("  " + " ".join(command))
    if plan.note:
        print(plan.note)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare OCR dependencies for Knowledge Bread Bakery.")
    parser.add_argument("--lang", default="chi_sim+eng", help="Tesseract languages to verify, default: chi_sim+eng.")
    parser.add_argument("--install", action="store_true", help="Run the detected install commands.")
    args = parser.parse_args()

    problems = check(args.lang)
    if not problems:
        print(f"OCR dependencies are ready for language setting: {args.lang}")
        return 0

    print("OCR dependencies are not ready:", file=sys.stderr)
    for problem in problems:
        print(f"- {problem}", file=sys.stderr)

    plan = detect_install_plan()
    print_plan(plan)

    if not args.install:
        print("\nRun again with `--install` to execute the suggested commands.", file=sys.stderr)
        return 1

    needs_system_install = any(
        problem in {"pdftoppm is missing", "tesseract is missing"} for problem in problems
    )

    if plan is None and needs_system_install:
        return 1

    if plan is not None and needs_system_install:
        for command in plan.commands:
            code = run(command)
            if code != 0:
                print(f"Install command failed with exit code {code}.", file=sys.stderr)
                return code

    add_windows_ocr_paths()
    try:
        install_windows_tessdata(args.lang)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    remaining = check(args.lang)
    if remaining:
        print("Install finished, but OCR is still not ready:", file=sys.stderr)
        for problem in remaining:
            print(f"- {problem}", file=sys.stderr)
        if plan.note:
            print(plan.note, file=sys.stderr)
        return 1

    print(f"OCR dependencies are ready for language setting: {args.lang}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
