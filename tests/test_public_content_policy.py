from __future__ import annotations

import subprocess
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".csv", ".json", ".md", ".py", ".sql", ".toml", ".txt", ".yaml", ".yml"}
SKIP_PARTS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "build",
    "dbt_packages",
    "dist",
    "evidence",
    "logs",
    "requirements",
    "target",
}
PROHIBITED_PATTERNS = {
    "employee email": re.compile(r"[\w.+-]+@snowflake[.]com", re.IGNORECASE),
    "workstation path": re.compile(r"/(?:Users|home)/[^/\s]+/"),
}


def _public_text_files():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    for name in result.stdout.splitlines():
        relative = Path(name)
        path = ROOT / relative
        if (
            path.is_file()
            and path.suffix.lower() in TEXT_SUFFIXES
            and relative != Path("tests/test_public_content_policy.py")
            and not SKIP_PARTS.intersection(relative.parts)
        ):
            yield relative, path


def test_public_tree_contains_no_private_environment_markers():
    findings = []
    for relative, path in _public_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in PROHIBITED_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{relative}: {label}")
    assert findings == []


def test_public_policy_keeps_internal_stage_as_product_terminology():
    policy = (ROOT / "docs/public-content-policy.md").read_text(encoding="utf-8")
    assert "internal\n  stages" in policy
    assert "employer-only" in policy


def test_only_neutral_enterprise_compatibility_fixtures_are_public():
    macro_names = sorted(path.name for path in (ROOT / "integration_tests/macros").glob("*compatibility*"))
    model_names = sorted(
        path.name for path in (ROOT / "integration_tests/models/agents").glob("*compatibility*")
    )
    assert macro_names == ["enterprise_compatibility.sql"]
    assert model_names == ["enterprise_compatibility_probe.sql"]