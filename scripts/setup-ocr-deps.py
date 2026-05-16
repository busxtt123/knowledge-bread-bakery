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
from dataclasses import dataclass


@dataclass(frozen=True)
class InstallPlan:
    manager: str
    commands: list[list[str]]
    note: str = ""


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
        text=True,
        errors="replace",
    )
    if result.returncode != 0:
        return set()

    langs: set[str] = set()
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped and not stripped.lower().startswith("list of available languages"):
            langs.add(stripped)
    return langs


def check(lang: str) -> list[str]:
    problems: list[str] = []
    if not command_exists("pdftoppm"):
        problems.append("pdftoppm is missing")
    if not command_exists("tesseract"):
        problems.append("tesseract is missing")
    else:
        requested = {part for part in lang.split("+") if part}
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
    parser = argparse.ArgumentParser(description="Prepare OCR dependencies for Knowledge Bread Machine.")
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

    if plan is None:
        return 1

    for command in plan.commands:
        code = run(command)
        if code != 0:
            print(f"Install command failed with exit code {code}.", file=sys.stderr)
            return code

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
