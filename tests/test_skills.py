from __future__ import annotations

import subprocess
from argparse import Namespace

import pytest

from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.manifest import SkillDeclaration
from dbt_cortex_agent.skills import (
    assert_apply_safety,
    build_upload_plan,
    upload_skills,
)


def _manifest(skills):
    return {
        "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
        "exposures": {
            f"exposure.test.{name}": {
                "name": name,
                "meta": {"cortex_agent": {"enabled": True, "capabilities": {"skills": values}}},
            }
            for name, values in skills.items()
        },
    }


def _skill(name, path):
    return {"name": name, "source": {"type": "stage", "path": path}}


def _config(tmp_path, **overrides):
    values = {
        "project_dir": str(tmp_path),
        "manifest": None,
        "target": "sandbox",
        "connection": "test",
        "database": "DB",
        "schema": "AGENTS",
        "role": None,
        "warehouse": None,
        "artifact_dir": None,
        "dbt_executable": "custom-dbt",
        "snow_executable": "custom-snow",
    } | overrides
    return resolve_config(Namespace(**values), env={})


def test_plan_deduplicates_shared_skill_and_filters_agents(tmp_path):
    skill_dir = tmp_path / "skills/library/shared"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Shared\n")
    shared = _skill("shared", "@DB.AGENTS.SKILL_STAGE/library/shared")
    manifest = _manifest({"agent_a": [shared], "agent_b": [shared]})

    plan = build_upload_plan(manifest, tmp_path)

    assert len(plan) == 1
    assert plan[0].agent_names == ("agent_a", "agent_b")
    assert plan[0].skill_names == ("shared",)
    assert build_upload_plan(manifest, tmp_path, ["agent_b"])[0].agent_names == ("agent_b",)


def test_plan_rejects_duplicate_skill_name_before_mutation(tmp_path):
    skill_dir = tmp_path / "skills/library/shared"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Shared\n")
    shared = _skill("shared", "@DB.AGENTS.SKILL_STAGE/library/shared")

    with pytest.raises(ValueError, match="duplicate skill name"):
        build_upload_plan(_manifest({"agent_a": [shared, shared]}), tmp_path)

    non_stage = {"name": "shared", "source": {"type": "git", "path": "repo/tag/skill"}}
    with pytest.raises(ValueError, match="duplicate skill name"):
        build_upload_plan(_manifest({"agent_a": [shared, non_stage]}), tmp_path)


def test_plan_rejects_missing_skill_file_and_private_ignore(tmp_path):
    shared = _skill("shared", "@DB.AGENTS.SKILL_STAGE/library/shared")
    with pytest.raises(FileNotFoundError, match="SKILL.md"):
        build_upload_plan(_manifest({"agent_a": [shared]}), tmp_path)

    private_dir = tmp_path / "models/agents/agent_a/skills/private"
    private_dir.mkdir(parents=True)
    (private_dir / "SKILL.md").write_text("# Private\n")
    private = _skill("private", "@DB.AGENTS.SKILL_STAGE/agents/agent_a/private")
    with pytest.raises(ValueError, match=".dbtignore"):
        build_upload_plan(_manifest({"agent_a": [private]}), tmp_path)

    (tmp_path / ".dbtignore").write_text("models/agents/*/skills/**\n")
    assert len(build_upload_plan(_manifest({"agent_a": [private]}), tmp_path)) == 1


def test_plan_rejects_distinct_local_sources_for_same_stage(monkeypatch, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    for directory in (first, second):
        directory.mkdir()
        (directory / "SKILL.md").write_text("# Skill\n")
    declarations = [
        SkillDeclaration("a", "one", "stage", "@DB.S.SKILLS/library/x", first),
        SkillDeclaration("b", "two", "stage", "@DB.S.SKILLS/library/x", second),
    ]
    monkeypatch.setattr(
        "dbt_cortex_agent.skills.skill_declarations", lambda *args, **kwargs: declarations
    )

    with pytest.raises(ValueError, match="collision"):
        build_upload_plan(_manifest({}), tmp_path)


def test_upload_uses_sse_configurable_snow_and_orders_stage_before_copy(tmp_path):
    skill_dir = tmp_path / "skills/library/shared"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Shared\n")
    plan = build_upload_plan(
        _manifest({"agent": [_skill("shared", "@DB.AGENTS.SKILL_STAGE/library/shared")]}),
        tmp_path,
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    upload_skills(plan, _config(tmp_path), CommandRunner(fake_run))

    assert calls[0][0:2] == ["custom-snow", "sql"]
    assert "SNOWFLAKE_SSE" in calls[0][-1]
    assert calls[1][0:3] == ["custom-snow", "stage", "copy"]


def test_apply_safety_requires_both_allowlists(tmp_path):
    config = _config(tmp_path)
    with pytest.raises(ValueError, match="allowed targets"):
        assert_apply_safety(config, [], ["DB"])
    with pytest.raises(ValueError, match="allowed databases"):
        assert_apply_safety(config, ["sandbox"], [])
    assert_apply_safety(config, ["sandbox"], ["db"])


@pytest.mark.parametrize(
    "path",
    [
        "@DB.AGENTS.STAGE/../secret",
        "@DB.AGENTS.STAGE/library/../../secret",
        "@DB.AGENTS.STAGE/library;drop/skill",
        '@"DB".AGENTS.STAGE/library/skill',
    ],
)
def test_stage_paths_reject_traversal_and_unsupported_identifiers(tmp_path, path):
    with pytest.raises(ValueError):
        build_upload_plan(_manifest({"agent": [_skill("bad", path)]}), tmp_path)
