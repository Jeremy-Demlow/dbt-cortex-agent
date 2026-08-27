from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
SKILL = ROOT / ".cortex/skills/dbt-cortex-agent-project/SKILL.md"


def test_project_skill_is_single_file_and_release_aware():
    text = SKILL.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])

    assert frontmatter["name"] == "dbt-cortex-agent-project"
    assert "0.0.5" not in frontmatter["description"]
    assert not (SKILL.parent / "scripts").exists()


def test_project_skill_preserves_materialization_ownership():
    text = SKILL.read_text(encoding="utf-8")

    assert "dbt build" in text
    assert "dbt-cortex-agent agent deploy" in text
    assert "dbt-cortex-agent eval verify" in text
    assert "require `0.0.5` or later" in text
    assert "materialized='cortex_agent'" in text or "materialized: cortex_agent" in text
    for removed in (
        "dbt-cortex-agent agent render",
        "dbt-cortex-agent agent grant",
        "dbt-cortex-agent agent promote",
        "dbt-cortex-agent agent rollback",
    ):
        assert removed not in text


def test_project_skill_uses_composed_package_workflows_without_wrappers():
    text = SKILL.read_text(encoding="utf-8")

    assert "dbt-cortex-agent eval run" not in text
    assert "project_runner.py" not in text
    assert "agent_gate.py" not in text
    assert "make dbt-focus" not in text
    assert "--role <ROLE>" in text
    assert "--baseline-dir <BASELINE_DIR>" in text


def test_project_skill_keeps_separate_approval_boundaries():
    text = SKILL.read_text(encoding="utf-8")
    stops = (
        "STOP 1",
        "STOP 2",
        "STOP 3",
        "STOP 4",
    )
    positions = [text.index(stop) for stop in stops]
    assert positions == sorted(positions)