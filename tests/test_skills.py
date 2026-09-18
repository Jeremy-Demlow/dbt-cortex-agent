from __future__ import annotations

import copy
import json
import subprocess
from argparse import Namespace
from functools import partial

import pytest
import yaml

from dbt_cortex_agent.cli import build_parser, main
from dbt_cortex_agent.commands.skill import handle
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.deployment import apply_deploy_plan, build_deploy_plan
from dbt_cortex_agent.domain import DurablePhaseError
from dbt_cortex_agent.invoke import smoke_skills
from dbt_cortex_agent.manifest import SkillDeclaration
from dbt_cortex_agent.skills import (
    assert_apply_safety,
    build_upload_plan,
    upload_skills,
)


def _manifest(skills):
    return {
        "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
        "exposures": {},
        "nodes": {
            f"model.test.{name}": {
                "unique_id": f"model.test.{name}",
                "resource_type": "model",
                "name": name,
                "database": "DB",
                "schema": "AGENTS",
                "alias": name.upper(),
                "config": {
                    "materialized": "cortex_agent",
                    "meta": {"cortex_agent": {"skills": values}},
                },
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


def test_upload_validates_existing_stage_before_copy(tmp_path):
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
    assert calls[0][-1] == "DESCRIBE STAGE DB.AGENTS.SKILL_STAGE"
    assert all("CREATE STAGE" not in " ".join(call) for call in calls)
    assert calls[1][0:3] == ["custom-snow", "stage", "copy"]


def test_upload_fails_before_copy_when_stage_is_missing(tmp_path):
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
        return subprocess.CompletedProcess(command, 1, "", "does not exist")

    with pytest.raises(RuntimeError, match="infrastructure owner"):
        upload_skills(plan, _config(tmp_path), CommandRunner(fake_run))

    assert len(calls) == 1


def test_upload_preflights_stages_across_databases_before_copy(tmp_path):
    for name in ("one", "two"):
        skill_dir = tmp_path / f"skills/library/{name}"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {name}\n")
    manifest = _manifest(
        {
            "agent_a": [_skill("one", "@DB_A.AGENTS.SKILL_STAGE/library/one")],
            "agent_b": [_skill("two", "@DB_B.AGENTS.SKILL_STAGE/library/two")],
        }
    )
    manifest["nodes"]["model.test.agent_a"]["database"] = "DB_A"
    manifest["nodes"]["model.test.agent_b"]["database"] = "DB_B"
    plan = build_upload_plan(manifest, tmp_path)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    upload_skills(plan, _config(tmp_path), CommandRunner(fake_run))

    assert [call[-1] for call in calls[:2]] == [
        "DESCRIBE STAGE DB_A.AGENTS.SKILL_STAGE",
        "DESCRIBE STAGE DB_B.AGENTS.SKILL_STAGE",
    ]
    assert all(call[1] == "sql" for call in calls[:2])
    assert all(call[1:3] == ["stage", "copy"] for call in calls[2:])


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


def _local_skills(tmp_path, names=("one", "two", "three")):
    skills = []
    for name in names:
        local = tmp_path / "skills/library" / name
        local.mkdir(parents=True)
        (local / "SKILL.md").write_text(f"# {name}\n")
        skills.append(_skill(name, f"@DB.AGENTS.SKILL_STAGE/library/{name}"))
    return skills


@pytest.mark.parametrize("field", ["raw_code", "compiled_code"])
@pytest.mark.parametrize("format_name", ["yaml", "json"])
def test_yaml_is_comparison_evidence_not_upload_authority(tmp_path, field, format_name):
    skills = _local_skills(tmp_path, ("one",))
    manifest = _manifest({"agent": skills})
    node = manifest["nodes"]["model.test.agent"]
    spec = {"skills": skills, "instructions": {"orchestration": "Use skills."}}
    node[field] = yaml.safe_dump(spec) if format_name == "yaml" else json.dumps(spec)
    assert build_upload_plan(manifest, tmp_path)[0].skill_names == ("one",)
    del node["config"]["meta"]["cortex_agent"]["skills"]
    with pytest.raises(ValueError, match="meta.cortex_agent.skills is required"):
        build_upload_plan(manifest, tmp_path)


@pytest.mark.parametrize("top_level_meta", [True, False])
def test_parse_only_metadata_discovers_jinja_declared_skills(tmp_path, top_level_meta):
    skills = _local_skills(tmp_path, ("one",))
    manifest = _manifest({"agent": skills})
    node = manifest["nodes"]["model.test.agent"]
    node["raw_code"] = "{{ config(materialized='cortex_agent') }}\nskills: {{ var('skills') }}"
    if top_level_meta:
        node["meta"] = node["config"].pop("meta")
    assert "compiled_code" not in node
    assert build_upload_plan(manifest, tmp_path)[0].stage_path == skills[0]["source"]["path"]


@pytest.mark.parametrize("field", ["name", "type", "path", "missing", "extra"])
def test_model_metadata_mismatch_fails_before_local_file_check(tmp_path, field):
    declared = [_skill("one", "@DB.AGENTS.SKILL_STAGE/library/one")]
    model_skills = copy.deepcopy(declared)
    if field == "name":
        model_skills[0]["name"] = "different"
    elif field in {"type", "path"}:
        model_skills[0]["source"][field] = (
            "git" if field == "type" else "@DB.AGENTS.SKILL_STAGE/library/other"
        )
    elif field == "missing":
        model_skills = []
    else:
        model_skills.append(_skill("two", "@DB.AGENTS.SKILL_STAGE/library/two"))
    manifest = _manifest({"agent": declared})
    manifest["nodes"]["model.test.agent"]["compiled_code"] = yaml.safe_dump(
        {"skills": model_skills}
    )
    with pytest.raises(ValueError, match="does not match model skills"):
        build_upload_plan(manifest, tmp_path)


@pytest.mark.parametrize(
    "declared",
    [
        None,
        {},
        "{{ var('skills') }}",
        [None],
        [{"name": "one"}],
        [_skill("one", "{{ var('stage') }}/library/one")],
        [{"name": "one", "source": {"type": "{{ source_type }}", "path": "x"}}],
    ],
)
def test_unresolved_or_malformed_metadata_is_not_an_empty_plan(tmp_path, declared):
    with pytest.raises(ValueError, match="meta.cortex_agent.skills"):
        build_upload_plan(_manifest({"agent": declared}), tmp_path)


@pytest.mark.parametrize(
    "body",
    ["skills: {{ var('skills') }}", "{{ render_skills() }}", "skills: [", "skills: null"],
)
def test_detectable_unresolved_body_cannot_silently_plan_empty(tmp_path, body):
    manifest = _manifest({"agent": []})
    manifest["nodes"]["model.test.agent"]["raw_code"] = body
    with pytest.raises(ValueError):
        build_upload_plan(manifest, tmp_path)


def test_skill_free_model_and_normalized_stage_identity(tmp_path):
    manifest = _manifest({"agent": []})
    node = manifest["nodes"]["model.test.agent"]
    node["raw_code"] = "instructions:\n  orchestration: Say hello\n"
    assert build_upload_plan(manifest, tmp_path) == []
    skills = _local_skills(tmp_path, ("one",))
    node["config"]["meta"]["cortex_agent"]["skills"] = skills
    model_skills = copy.deepcopy(skills)
    model_skills[0]["source"]["path"] = "@db.agents.skill_stage/library/one"
    node["compiled_code"] = yaml.safe_dump({"skills": model_skills})
    assert build_upload_plan(manifest, tmp_path)[0].stage_fqn == "DB.AGENTS.SKILL_STAGE"


@pytest.mark.parametrize("location", ["metadata", "model"])
def test_legacy_capabilities_location_fails_actionably(tmp_path, location):
    manifest = _manifest({"agent": []})
    node = manifest["nodes"]["model.test.agent"]
    if location == "metadata":
        node["config"]["meta"]["cortex_agent"]["capabilities"] = {"skills": []}
    else:
        node["compiled_code"] = "capabilities:\n  skills: []\n"
    with pytest.raises(ValueError, match="capabilities.skills"):
        build_upload_plan(manifest, tmp_path)


@pytest.mark.parametrize("failure_kind", ["exit", "oserror", "timeout"])
def test_later_copy_preserves_each_destination_and_stops(tmp_path, failure_kind):
    skills = _local_skills(tmp_path)
    plan = build_upload_plan(_manifest({"agent": skills}), tmp_path)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[1:3] == ["stage", "copy"] and command[-5].endswith("/three/"):
            if failure_kind == "oserror":
                raise OSError("copy unavailable")
            if failure_kind == "timeout":
                raise subprocess.TimeoutExpired(command, 1)
            return subprocess.CompletedProcess(command, 1, "", "later copy failed")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    with pytest.raises(DurablePhaseError) as caught:
        upload_skills(plan, _config(tmp_path, role="APPROVED_ROLE"), CommandRunner(run))
    phases = caught.value.outcome.to_dict()
    assert [(phase["stage_path"], phase["completed"]) for phase in phases] == [
        (plan[0].stage_path, True),
        (plan[1].stage_path, False),
    ]
    assert "partial effects possible" in phases[1]["detail"]
    assert len(calls) == 3
    assert all(command[command.index("--role") + 1] == "APPROVED_ROLE" for command in calls)


@pytest.mark.parametrize("domain", ["skill", "agent"])
@pytest.mark.parametrize("json_output", [True, False])
def test_cli_later_copy_retains_outcomes_and_role_override(
    tmp_path, monkeypatch, capsys, domain, json_output
):
    skills = _local_skills(tmp_path)
    manifest = _manifest({"agent": skills})
    calls = []
    key = tmp_path / "synthetic.p8"
    key.write_text("synthetic key fixture")

    def run(self, command, **kwargs):
        calls.append(command)
        if command[1:3] == ["connection", "list"]:
            payload = [
                {
                    "connection_name": "named",
                    "parameters": {
                        "account": "synthetic",
                        "user": "synthetic",
                        "database": "DB",
                        "role": "CONNECTION_ROLE",
                        "private_key_file": str(key),
                    },
                }
            ]
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        if command[1:3] == ["stage", "copy"] and command[-5].endswith("/three/"):
            return subprocess.CompletedProcess(command, 1, "", "later copy failed")
        assert command[1] != "build", "deploy must stop after partial upload"
        return subprocess.CompletedProcess(command, 0, "ok", "")

    def fresh(config, **kwargs):
        assert config.role == "APPROVED_ROLE"
        assert config.dbt_env["SNOWFLAKE_ROLE"] == "APPROVED_ROLE"
        return manifest

    monkeypatch.setattr(CommandRunner, "run", run)
    monkeypatch.setattr(f"dbt_cortex_agent.commands.{domain}.fresh_manifest", fresh)
    argv = [
        domain,
        "upload" if domain == "skill" else "deploy",
        "--project-dir",
        str(tmp_path),
        "--agent",
        "agent",
        "--target",
        "sandbox",
        "--connection",
        "named",
        "--role",
        "APPROVED_ROLE",
        "--allow-target",
        "sandbox",
        "--allow-database",
        "DB",
        "--apply",
    ]
    assert main([*argv, *(["--json"] if json_output else [])]) == 2
    output = capsys.readouterr()
    assert output.err == ""
    if json_output or domain == "agent":
        payload = json.loads(output.out)
        phases = [phase for phase in payload["phases"] if "stage_path" in phase]
        assert [(phase["stage_path"], phase["completed"]) for phase in phases] == [
            (skills[0]["source"]["path"], True),
            (skills[2]["source"]["path"], False),
        ]
        assert payload["status"] == "partial_failure"
    else:
        assert f"{skills[0]['source']['path']}: completed=True" in output.out
        assert f"{skills[2]['source']['path']}: completed=False" in output.out
    assert len(calls) == 4
    assert all(command[command.index("--role") + 1] == "APPROVED_ROLE" for command in calls[1:])


def test_skill_smoke_passes_role_through_command_and_runtime(tmp_path, monkeypatch, capsys):
    manifest = _manifest({"agent": [_skill("one", "@DB.AGENTS.SKILL_STAGE/library/one")]})
    monkeypatch.setattr("dbt_cortex_agent.commands.skill.fresh_manifest", lambda *a, **k: manifest)
    calls = []

    def invoke(*args, **kwargs):
        calls.append((args, kwargs))
        return {"tool_uses": [{"name": "server_skill", "input": {"skill_name": "one"}}]}

    monkeypatch.setattr(
        "dbt_cortex_agent.commands.skill.smoke_skills", partial(smoke_skills, invoker=invoke)
    )
    args = build_parser().parse_args(
        [
            "skill",
            "smoke",
            "--agent",
            "agent",
            "--apply",
            "--allow-target",
            "sandbox",
            "--allow-database",
            "DB",
            "--json",
        ]
    )
    assert handle(args, _config(tmp_path, role="APPROVED_ROLE")) == 0
    assert calls[0][1] == {"role": "APPROVED_ROLE"}
    assert calls[0][0][:3] == ("DB", "AGENTS", "AGENT")
    assert json.loads(capsys.readouterr().out)["verified"] == ["one"]


@pytest.mark.parametrize(
    "body", ["skills: {{ var('skills') }}", "skills: [", "- not-a-mapping", "skills: null"]
)
def test_invalid_compiled_evidence_is_not_hidden_by_valid_metadata(tmp_path, body):
    skills = _local_skills(tmp_path, ("one",))
    manifest = _manifest({"agent": skills})
    manifest["nodes"]["model.test.agent"]["compiled_code"] = body
    with pytest.raises(ValueError):
        build_upload_plan(manifest, tmp_path)


def test_compiled_instruction_placeholders_do_not_invalidate_skill_contract(tmp_path):
    skills = _local_skills(tmp_path, ("one",))
    manifest = _manifest({"agent": skills})
    manifest["nodes"]["model.test.agent"]["compiled_code"] = yaml.safe_dump(
        {"skills": skills, "instructions": {"response": "Discuss {{input}} as literal text"}}
    )
    assert build_upload_plan(manifest, tmp_path)[0].skill_names == ("one",)


@pytest.mark.parametrize("error_type", [AssertionError, TypeError, AttributeError])
def test_copy_programming_errors_propagate(tmp_path, error_type):
    plan = build_upload_plan(_manifest({"agent": _local_skills(tmp_path)}), tmp_path)

    def run(command, **kwargs):
        if command[1:3] == ["stage", "copy"]:
            raise error_type("programming defect")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    with pytest.raises(error_type, match="programming defect"):
        upload_skills(plan, _config(tmp_path), CommandRunner(run))


def test_later_stage_preflight_failure_prevents_every_copy(tmp_path):
    skills = _local_skills(tmp_path, ("one", "two"))
    skills[1]["source"]["path"] = "@DB.AGENTS.Z_STAGE/library/two"
    plan = build_upload_plan(_manifest({"agent": skills}), tmp_path)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert command[1] == "sql"
        return subprocess.CompletedProcess(command, int(len(calls) == 2), "", "not accessible")

    with pytest.raises(DurablePhaseError) as caught:
        upload_skills(plan, _config(tmp_path), CommandRunner(run))
    assert len(calls) == 2
    phases = caught.value.outcome.to_dict()
    assert len(phases) == 1
    assert phases[0]["phase"] == "preflight"
    assert phases[0]["stage_path"] == plan[1].stage_path
    assert phases[0]["completed"] is False


@pytest.mark.parametrize("build_fails", [True, False])
def test_deploy_retains_successful_destinations_after_build(tmp_path, build_fails):
    manifest = _manifest({"agent": _local_skills(tmp_path)})
    config = _config(tmp_path, role="APPROVED_ROLE")
    plan = build_deploy_plan(manifest, config, ["agent"])
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command, int(build_fails and command[1] == "build"), "build output", ""
        )

    if build_fails:
        with pytest.raises(DurablePhaseError) as caught:
            apply_deploy_plan(plan, config, runner=CommandRunner(run))
        outcome = caught.value.outcome
    else:
        outcome = apply_deploy_plan(plan, config, runner=CommandRunner(run))
    destinations = [phase for phase in outcome.to_dict() if "stage_path" in phase]
    assert [phase["stage_path"] for phase in destinations] == [
        item.stage_path for item in plan.skill_uploads
    ]
    assert all(phase["completed"] for phase in destinations)
    assert calls[-1][1] == "build"
    assert outcome.phases[-1].completed is not build_fails


def test_skill_preview_does_not_upload_or_invoke(tmp_path, monkeypatch, capsys):
    manifest = _manifest({"agent": _local_skills(tmp_path, ("one",))})
    monkeypatch.setattr("dbt_cortex_agent.commands.skill.fresh_manifest", lambda *a, **k: manifest)
    monkeypatch.setattr(CommandRunner, "run", lambda *a, **k: pytest.fail("unexpected effect"))
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.skill.smoke_skills",
        lambda *a, **k: pytest.fail("unexpected runtime"),
    )
    for action in ("plan", "upload", "smoke"):
        args = build_parser().parse_args(["skill", action, "--agent", "agent", "--json"])
        assert handle(args, _config(tmp_path)) == 0
        assert json.loads(capsys.readouterr().out)["applied"] is False
