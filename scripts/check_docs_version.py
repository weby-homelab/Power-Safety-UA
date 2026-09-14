#!/usr/bin/env python3
"""Verify that public documentation reports the release version from VERSION."""

from __future__ import annotations

import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"v\d+\.\d+\.\d+")
RELEASE_HEADING_PATTERN = re.compile(r"## \[([^\]\n]+)\] - \d{4}-\d{2}-\d{2}")


def read_project_file(relative_path: str) -> str:
    path = PROJECT_ROOT / relative_path
    if path.is_symlink():
        raise ValueError(f"{relative_path} must not be a symlink")
    try:
        path.resolve(strict=False).relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError(f"{relative_path} must remain inside the project") from error
    return path.read_text(encoding="utf-8")


def read_release_version() -> str:
    version = read_project_file("VERSION").strip()
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError("VERSION must contain a semantic vX.Y.Z release version")
    return version


def first_release_heading_is_current(content: str, expected: str) -> bool:
    first_heading = next(
        (line for line in content.splitlines() if line.startswith("## [")),
        None,
    )
    if first_heading is None:
        return False
    match = RELEASE_HEADING_PATTERN.fullmatch(first_heading)
    return match is not None and match.group(1) == expected


def main() -> int:
    try:
        version = read_release_version()
    except (OSError, ValueError) as error:
        print(f"Documentation version check failed: {error}", file=sys.stderr)
        return 1

    version_number = version.removeprefix("v")
    marker_checks = (
        ("app/_version.py", r'^__version__ = "(v\d+\.\d+\.\d+)"$', version),
        ("README.md", r"Stable (v\d+\.\d+\.\d+)", version),
        ("README.md", r"^softwareVersion: (\d+\.\d+\.\d+)$", version_number),
        ("README_ENG.md", r"Stable (v\d+\.\d+\.\d+)", version),
        ("README_ENG.md", r"^softwareVersion: (\d+\.\d+\.\d+)$", version_number),
        ("docs_site/index.md", r"Stable \((v\d+\.\d+\.\d+)\)", version),
    )
    top_heading_checks = (
        ("CHANGELOG.md", version_number),
        ("docs/CHANGELOG.md", version),
    )

    failures: list[str] = []
    loaded_files: dict[str, str] = {}
    for relative_path, pattern, expected in marker_checks:
        if relative_path not in loaded_files:
            try:
                loaded_files[relative_path] = read_project_file(relative_path)
            except (OSError, UnicodeError, ValueError) as error:
                failures.append(f"{relative_path}: {error}")
                continue
        matches = re.findall(pattern, loaded_files[relative_path], flags=re.MULTILINE)
        if matches != [expected]:
            failures.append(
                f"{relative_path}: expected exactly one current version marker {expected!r}"
            )

    for relative_path, expected in top_heading_checks:
        if relative_path not in loaded_files:
            try:
                loaded_files[relative_path] = read_project_file(relative_path)
            except (OSError, UnicodeError, ValueError) as error:
                failures.append(f"{relative_path}: {error}")
                continue
        if not first_release_heading_is_current(loaded_files[relative_path], expected):
            failures.append(
                f"{relative_path}: first release heading must use {expected!r}"
            )

    release_notes = loaded_files.get("release_notes.md")
    if release_notes is None:
        try:
            release_notes = read_project_file("release_notes.md")
            loaded_files["release_notes.md"] = release_notes
        except (OSError, UnicodeError, ValueError) as error:
            failures.append(f"release_notes.md: {error}")
    if release_notes is not None and not release_notes.startswith(
        f"# Release {version}\n"
    ):
        failures.append(f"release_notes.md: first heading must be # Release {version}")

    if failures:
        print("Documentation version check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"Documentation version check passed: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
