from __future__ import annotations

import argparse
import re
import subprocess
from datetime import date
from pathlib import Path


TAG_PATTERN = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")
PYPROJECT_VERSION = re.compile(r'^version\s*=\s*"([^"]+)"\s*$', re.MULTILINE)
DBT_VERSION = re.compile(r"^version:\s*['\"]?([^'\"\s]+)['\"]?\s*$", re.MULTILINE)


def _read_version(path: Path, pattern: re.Pattern[str], label: str) -> str:
    match = pattern.search(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"could not read {label} version from {path}")
    return match.group(1)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_release(root: Path, tag: str) -> str:
    tag_match = TAG_PATTERN.fullmatch(tag)
    if not tag_match:
        raise ValueError(f"release tag must match vMAJOR.MINOR.PATCH: {tag}")
    version = tag_match.group("version")

    dirty = _git(root, "status", "--porcelain", "--untracked-files=all")
    if dirty:
        raise ValueError("release checkout is not clean")

    tags_at_head = set(_git(root, "tag", "--points-at", "HEAD").splitlines())
    if tag not in tags_at_head:
        raise ValueError(f"release tag {tag} does not point at HEAD")

    python_version = _read_version(root / "pyproject.toml", PYPROJECT_VERSION, "Python package")
    dbt_version = _read_version(root / "dbt_project.yml", DBT_VERSION, "dbt package")
    if python_version != version or dbt_version != version:
        raise ValueError(
            f"release version mismatch: tag={version}, python={python_version}, dbt={dbt_version}"
        )

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = re.search(rf"^##\s+{re.escape(version)}\s+—\s+(.+?)\s*$", changelog, re.MULTILINE)
    if not heading:
        raise ValueError(f"CHANGELOG.md has no heading for {version}")
    release_marker = heading.group(1).strip()
    if release_marker.lower() == "unreleased":
        raise ValueError(f"CHANGELOG.md still marks {version} as Unreleased")
    try:
        date.fromisoformat(release_marker)
    except ValueError:
        raise ValueError(f"CHANGELOG.md release heading must use YYYY-MM-DD: {release_marker}")

    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a clean, version-aligned release tag.")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        version = validate_release(args.project_root.resolve(), args.tag)
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))
    print(f"release preflight passed for {args.tag} ({version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
