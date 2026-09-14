import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_documentation_homepage_matches_release_version() -> None:
    version = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    version_number = version.removeprefix("v")
    homepage = (PROJECT_ROOT / "docs_site" / "index.md").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    readme_english = (PROJECT_ROOT / "README_ENG.md").read_text(encoding="utf-8")
    release_notes = (PROJECT_ROOT / "release_notes.md").read_text(encoding="utf-8")

    assert f"Stable ({version})" in homepage
    assert f"Stable {version}" in readme
    assert f"Stable {version}" in readme_english
    assert f"softwareVersion: {version_number}" in readme
    assert f"softwareVersion: {version_number}" in readme_english
    assert release_notes.startswith(f"# Release {version}\n")


def test_documentation_version_checker_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "check_docs_version.py")],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
