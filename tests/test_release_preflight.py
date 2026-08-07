from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/release_preflight.py"
SPEC = importlib.util.spec_from_file_location("release_preflight", SCRIPT)
assert SPEC and SPEC.loader
release_preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_preflight)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _release_repo(tmp_path: Path, *, python_version: str = "0.3.1", dbt_version: str = "0.3.1", marker: str = "2026-08-07") -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "dbt-cortex-agent"\nversion = "{python_version}"\n', encoding="utf-8"
    )
    (tmp_path / "dbt_project.yml").write_text(
        f"name: 'dbt_cortex_agent'\nversion: '{dbt_version}'\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## 0.3.1 — {marker}\n\n- Release.\n", encoding="utf-8"
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Release Test")
    _git(tmp_path, "config", "user.email", "release-test@example.invalid")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "release fixture")
    _git(tmp_path, "tag", "v0.3.1")
    return tmp_path


def test_v031_release_preflight_passes_for_clean_aligned_tag(tmp_path: Path) -> None:
    root = _release_repo(tmp_path)
    assert release_preflight.validate_release(root, "v0.3.1") == "0.3.1"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(root), "--tag", "v0.3.1"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "release preflight passed for v0.3.1 (0.3.1)"


@pytest.mark.parametrize("tag", ["0.3.1", "v0.3", "release-v0.3.1"])
def test_release_preflight_rejects_malformed_tag(tmp_path: Path, tag: str) -> None:
    root = _release_repo(tmp_path)
    with pytest.raises(ValueError, match="must match"):
        release_preflight.validate_release(root, tag)


def test_release_preflight_rejects_tag_not_at_head(tmp_path: Path) -> None:
    root = _release_repo(tmp_path)
    (root / "later.txt").write_text("later\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "later")
    with pytest.raises(ValueError, match="does not point at HEAD"):
        release_preflight.validate_release(root, "v0.3.1")


def test_release_preflight_rejects_dirty_checkout(tmp_path: Path) -> None:
    root = _release_repo(tmp_path)
    (root / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not clean"):
        release_preflight.validate_release(root, "v0.3.1")


@pytest.mark.parametrize(
    ("python_version", "dbt_version"),
    [("0.3.2", "0.3.1"), ("0.3.1", "0.3.2")],
)
def test_release_preflight_rejects_version_mismatch(
    tmp_path: Path, python_version: str, dbt_version: str
) -> None:
    root = _release_repo(tmp_path, python_version=python_version, dbt_version=dbt_version)
    with pytest.raises(ValueError, match="version mismatch"):
        release_preflight.validate_release(root, "v0.3.1")


@pytest.mark.parametrize("marker", ["Unreleased", "August 5, 2026", "2026-99-99"])
def test_release_preflight_rejects_unreleased_or_undated_changelog(
    tmp_path: Path, marker: str
) -> None:
    root = _release_repo(tmp_path, marker=marker)
    with pytest.raises(ValueError, match="Unreleased|YYYY-MM-DD"):
        release_preflight.validate_release(root, "v0.3.1")


def test_release_preflight_rejects_missing_changelog_entry(tmp_path: Path) -> None:
    root = _release_repo(tmp_path)
    (root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    _git(root, "add", "CHANGELOG.md")
    _git(root, "commit", "-qm", "remove release entry")
    _git(root, "tag", "-f", "v0.3.1")
    with pytest.raises(ValueError, match="no heading"):
        release_preflight.validate_release(root, "v0.3.1")
