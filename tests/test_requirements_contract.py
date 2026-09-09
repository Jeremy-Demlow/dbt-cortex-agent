from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
ACTIVE_REQUIREMENTS = range(21, 32)
EVIDENCE_GLOBS = ("tests/*.py", "scripts/*.py")


def _requirement_path(number: int) -> Path:
    matches = tuple((ROOT / "requirements").glob(f"REQ-{number:03d}_*.md"))
    assert len(matches) == 1, f"REQ-{number:03d} must have exactly one tracked file"
    return matches[0]


def test_active_requirements_are_indexed_and_linked() -> None:
    index = (ROOT / "requirements/README.md").read_text(encoding="utf-8")
    stories = (ROOT / "requirements/user_stories.md").read_text(encoding="utf-8")
    cases = (ROOT / "tests/test_cases.md").read_text(encoding="utf-8")

    for number in ACTIVE_REQUIREMENTS:
        requirement = _requirement_path(number)
        prefix = f"REQ-{number:03d}"
        assert requirement.name in index
        assert f"## {prefix}" in stories
        assert f"## {prefix}:" in cases


def test_every_active_acceptance_criterion_has_a_test_case() -> None:
    cases = (ROOT / "tests/test_cases.md").read_text(encoding="utf-8")

    for number in ACTIVE_REQUIREMENTS:
        text = _requirement_path(number).read_text(encoding="utf-8")
        acceptance = text.split("## Acceptance Criteria", 1)[1].split("\n## ", 1)[0]
        criterion_numbers = [int(value) for value in re.findall(r"(?m)^(\d+)\. ", acceptance)]
        assert criterion_numbers == list(range(1, len(criterion_numbers) + 1))
        for criterion in criterion_numbers:
            assert f"TC-{number:03d}-{criterion:02d}" in cases


def test_every_active_test_case_has_executable_evidence() -> None:
    evidence_files = tuple(
        path
        for pattern in EVIDENCE_GLOBS
        for path in ROOT.glob(pattern)
        if path.name != "test_cases.md"
    )
    evidence = "\n".join(path.read_text(encoding="utf-8") for path in evidence_files)

    for number in ACTIVE_REQUIREMENTS:
        text = _requirement_path(number).read_text(encoding="utf-8")
        acceptance = text.split("## Acceptance Criteria", 1)[1].split("\n## ", 1)[0]
        criterion_count = len(re.findall(r"(?m)^\d+\. ", acceptance))
        for criterion in range(1, criterion_count + 1):
            test_case = f"TC-{number:03d}-{criterion:02d}"
            assert test_case in evidence, f"{test_case} has no executable evidence marker"


def test_private_preview_features_do_not_become_scaffold_options() -> None:
    requirement = _requirement_path(24).read_text(encoding="utf-8")

    assert "does not require a Semantic View" in requirement
    assert "no private-preview key receives a package-specific CLI option" in requirement
    assert "Cortex Sense-specific CLI flags" in requirement
