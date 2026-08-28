from __future__ import annotations

import json
from pathlib import Path

from dbt_cortex_agent.cli import (
    EXIT_CONTROLLED_ERROR,
    EXIT_DIAGNOSTIC_FAILURE,
    EXIT_SUCCESS,
    build_parser,
)

ROOT = Path(__file__).parents[1]

# Evidence: TC-021-10


def _choices(parser):
    return next(action.choices for action in parser._actions if getattr(action, "choices", None))


def test_v005_compatibility_snapshot_matches_supported_surface() -> None:
    snapshot = json.loads(
        (ROOT / "tests/fixtures/compatibility/0.0.5.json").read_text(encoding="utf-8")
    )
    parser = build_parser()
    domains = _choices(parser)
    agent_commands = _choices(domains["agent"])

    assert snapshot["top_level_commands"] == sorted(domains)
    assert set(snapshot["agent_commands"]).issubset(agent_commands)
    assert snapshot["exit_codes"] == {
        "success": EXIT_SUCCESS,
        "quality_or_diagnostic_failure": EXIT_DIAGNOSTIC_FAILURE,
        "controlled_error": EXIT_CONTROLLED_ERROR,
    }
    assert snapshot["python_agent_ddl"] is False


def test_v005_snapshot_marks_new_lifecycle_commands_as_additive() -> None:
    snapshot = json.loads(
        (ROOT / "tests/fixtures/compatibility/0.0.5.json").read_text(encoding="utf-8")
    )
    notes = " ".join(snapshot["notes"])

    for command in ("promote", "rollback", "versions", "drop", "scaffold"):
        assert command in notes
    assert "not compatibility APIs" in notes
