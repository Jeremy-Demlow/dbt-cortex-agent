from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from argparse import Namespace
from functools import partial
from pathlib import Path

import pytest
import yaml

from dbt_cortex_agent.cli import build_parser, main
from dbt_cortex_agent.commands.skill import handle
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.deployment import apply_deploy_plan, build_deploy_plan
from dbt_cortex_agent.domain import DurablePhaseError
from dbt_cortex_agent.invoke import smoke_skills
from dbt_cortex_agent.manifest import SkillDeclaration, skill_declarations
from dbt_cortex_agent.skills import (
    assert_apply_safety,
    build_upload_plan,
    skill_digests,
    skill_inventory,
    upload_skills,
)


def _copy_destination(command):
    return command[-6]


def _reconciled_output(agent_fqn):
    marker = {"agent_fqn": agent_fqn, "phase": "live_reconciled"}
    return "CORTEX_AGENT_DEPLOY_PHASE=" + json.dumps(marker)


class FakeStage:
    """Snow CLI double: answers DESCRIBE and LIST and records copied file content."""

    def __init__(self, files=None, *, fail_copy=None, drop_on_copy=()):
        self.files = dict(files or {})  # (stage fqn, path under stage) -> (size, md5)
        self.calls = []
        self.fail_copy = fail_copy
        self.drop_on_copy = set(drop_on_copy)

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if command[1] == "sql" and command[-1].startswith("LIST "):
            stage, prefix = command[-1][len("LIST @") :].split("/", 1)
            rows = [
                {"name": f"{name.split('.')[-1].lower()}/{path}", "size": size, "md5": md5}
                for (name, path), (size, md5) in sorted(self.files.items())
                if name == stage and path.startswith(prefix)
            ]
            return subprocess.CompletedProcess(command, 0, json.dumps(rows), "")
        if command[1] == "build":
            return subprocess.CompletedProcess(
                command, 0, _reconciled_output("DB.AGENTS.AGENT"), ""
            )
        if command[1:3] == ["stage", "copy"]:
            if self.fail_copy:
                failure = self.fail_copy(command)
                if failure is not None:
                    return failure
            stage, folder = _copy_destination(command)[1:].rstrip("/").split("/", 1)
            source = Path(command[-7]).parent
            for path in source.rglob("*"):
                relative = path.relative_to(source).as_posix()
                key = (stage, f"{folder}/{relative}")
                if not path.is_file() or relative in self.drop_on_copy:
                    continue
                if key in self.files and "--no-overwrite" in command:
                    continue
                data = path.read_bytes()
                self.files[key] = (len(data), hashlib.md5(data).hexdigest())
        return subprocess.CompletedProcess(command, 0, "ok", "")

    def copies(self):
        return [call for call in self.calls if call[1:3] == ["stage", "copy"]]


def _manifest(skills):
    return {
        "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
        "exposures": {},
        "nodes": {
            f"model.test.{name}": {
                "unique_id": f"model.test.{name}",
                "resource_type": "model",
                "name": name,
                "fqn": ["test", "agents", name, name],
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

    non_stage = {"name": "shared", "source": {"type": "workspace", "path": "repo/tag/skill"}}
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
    stage = FakeStage()

    upload_skills(plan, _config(tmp_path), CommandRunner(stage))

    calls = stage.calls
    assert calls[0][0:2] == ["custom-snow", "sql"]
    assert calls[0][-1] == "DESCRIBE STAGE DB.AGENTS.SKILL_STAGE"
    assert all("CREATE STAGE" not in " ".join(call) for call in calls)
    assert calls[1][-1] == f"LIST {plan[0].deployed_path}/"
    assert calls[2][0:3] == ["custom-snow", "stage", "copy"]
    assert calls[3][-1] == f"LIST {plan[0].deployed_path}/"


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
    stage = FakeStage()

    upload_skills(plan, _config(tmp_path), CommandRunner(stage))

    calls = stage.calls
    assert [call[-1] for call in calls[:2]] == [
        "DESCRIBE STAGE DB_A.AGENTS.SKILL_STAGE",
        "DESCRIBE STAGE DB_B.AGENTS.SKILL_STAGE",
    ]
    assert all(call[1] == "sql" for call in calls[:2])
    assert len(stage.copies()) == 2 and calls.index(stage.copies()[0]) > 2


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
            "workspace" if field == "type" else "@DB.AGENTS.SKILL_STAGE/library/other"
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

    def fail(command):
        if "/three/" not in _copy_destination(command):
            return None
        if failure_kind == "oserror":
            raise OSError("copy unavailable")
        if failure_kind == "timeout":
            raise subprocess.TimeoutExpired(command, 1)
        return subprocess.CompletedProcess(command, 1, "", "later copy failed")

    stage = FakeStage(fail_copy=fail)
    with pytest.raises(DurablePhaseError) as caught:
        upload_skills(plan, _config(tmp_path, role="APPROVED_ROLE"), CommandRunner(stage))
    phases = caught.value.outcome.to_dict()
    assert [(phase["stage_path"], phase["completed"]) for phase in phases] == [
        (plan[0].deployed_path, True),
        (plan[1].deployed_path, False),
    ]
    assert "partial effects possible" in phases[1]["detail"]
    assert len(stage.copies()) == 2
    assert all("/two/" not in _copy_destination(command) for command in stage.copies())
    assert all(command[command.index("--role") + 1] == "APPROVED_ROLE" for command in stage.calls)


@pytest.mark.parametrize("domain", ["skill", "agent"])
@pytest.mark.parametrize("json_output", [True, False])
def test_cli_later_copy_retains_outcomes_and_role_override(
    tmp_path, monkeypatch, capsys, domain, json_output
):
    skills = _local_skills(tmp_path)
    manifest = _manifest({"agent": skills})
    key = tmp_path / "synthetic.p8"
    key.write_text("synthetic key fixture")
    stage = FakeStage(
        fail_copy=lambda command: (
            subprocess.CompletedProcess(command, 1, "", "later copy failed")
            if "/three/" in _copy_destination(command)
            else None
        )
    )
    calls = stage.calls

    def run(self, command, **kwargs):
        if command[1:3] == ["connection", "list"]:
            calls.append(command)
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
        assert command[1] != "build", "deploy must stop after partial upload"
        return stage(command, **kwargs)

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
    deployed = [path for path, _ in _deployed_paths(tmp_path, manifest)]
    if json_output or domain == "agent":
        payload = json.loads(output.out)
        phases = [phase for phase in payload["phases"] if "stage_path" in phase]
        assert [(phase["stage_path"], phase["completed"]) for phase in phases] == [
            (deployed[0], True),
            (deployed[1], False),
        ]
        assert payload["status"] == "partial_failure"
    else:
        assert f"{deployed[0]}: completed=True" in output.out
        assert f"{deployed[1]}: completed=False" in output.out
    assert len(stage.copies()) == 2
    assert all(command[command.index("--role") + 1] == "APPROVED_ROLE" for command in calls[1:])


def _deployed_paths(tmp_path, manifest):
    return [
        (item.deployed_path, item.skill_names) for item in build_upload_plan(manifest, tmp_path)
    ]


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

    def fail(command):
        raise error_type("programming defect")

    with pytest.raises(error_type, match="programming defect"):
        upload_skills(plan, _config(tmp_path), CommandRunner(FakeStage(fail_copy=fail)))


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
    stage = FakeStage()

    def run(command, **kwargs):
        if command[1] == "build":
            stage.calls.append(command)
            return subprocess.CompletedProcess(
                command, int(build_fails), _reconciled_output("DB.AGENTS.AGENT"), ""
            )
        return stage(command, **kwargs)

    if build_fails:
        with pytest.raises(DurablePhaseError) as caught:
            apply_deploy_plan(plan, config, runner=CommandRunner(run))
        outcome = caught.value.outcome
    else:
        outcome = apply_deploy_plan(plan, config, runner=CommandRunner(run))
    destinations = [phase for phase in outcome.to_dict() if "stage_path" in phase]
    assert [phase["stage_path"] for phase in destinations] == [
        item.deployed_path for item in plan.skill_uploads
    ]
    assert all(phase["completed"] for phase in destinations)
    assert stage.calls[-1][1] == "build"
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


# Skill modes: committed Agent versions read skills live, so only a path whose
# content never changes lets a rollback restore the skill text.

GIT_PATH = "@DB.AGENTS.SKILLS_REPO/commits/" + "a" * 40 + "/skills/one"


def _skill_dir(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return root


def test_inventory_digest_tracks_published_content_only(tmp_path):
    first = _skill_dir(tmp_path / "a", {"SKILL.md": "# One\n", "scripts/run.py": "print(1)\n"})
    second = _skill_dir(tmp_path / "b", {"scripts/run.py": "print(1)\n", "SKILL.md": "# One\n"})
    (second / ".DS_Store").write_text("finder")
    _skill_dir(second / ".cache", {"note.txt": "local only"})

    files, digest = skill_inventory(first)
    assert skill_inventory(second) == (files, digest)
    assert digest.startswith("sha256-") and len(digest) == len("sha256-") + 16
    assert [item.relative_path for item in files] == ["SKILL.md", "scripts/run.py"]

    (second / "SKILL.md").write_text("# One, revised\n")
    assert skill_inventory(second)[1] != digest
    renamed = _skill_dir(tmp_path / "c", {"SKILL.md": "# One\n", "scripts/go.py": "print(1)\n"})
    assert skill_inventory(renamed)[1] != digest


def test_inventory_rejects_symlinks_and_unsafe_file_names(tmp_path):
    linked = _skill_dir(tmp_path / "linked", {"SKILL.md": "# One\n"})
    (linked / "alias.md").symlink_to(linked / "SKILL.md")
    with pytest.raises(ValueError, match="symlink"):
        skill_inventory(linked)
    spaced = _skill_dir(tmp_path / "spaced", {"SKILL.md": "# One\n", "my notes.md": "x"})
    with pytest.raises(ValueError, match="must use only"):
        skill_inventory(spaced)


def test_immutable_default_uploads_to_content_folder_and_reuses_it(tmp_path):
    skills = _local_skills(tmp_path, ("one",))
    plan = build_upload_plan(_manifest({"agent": skills}), tmp_path)
    base = skills[0]["source"]["path"]
    upload = plan[0]
    assert upload.mode == "immutable"
    assert upload.deployed_path == f"{base}/{upload.digest}"
    assert skill_digests(plan) == {base: upload.digest}

    stage = FakeStage()
    first = upload_skills(plan, _config(tmp_path), CommandRunner(stage))
    assert [phase.detail for phase in first.phases] == ["uploaded"]
    assert [_copy_destination(command) for command in stage.copies()] == [
        f"{upload.deployed_path}/"
    ]
    assert "--no-overwrite" in stage.copies()[0] and "--no-auto-compress" in stage.copies()[0]

    second = upload_skills(plan, _config(tmp_path), CommandRunner(stage))
    assert [phase.detail for phase in second.phases] == ["reused"]
    assert len(stage.copies()) == 1


def test_changed_skill_gets_new_folder_and_leaves_prior_folder_untouched(tmp_path):
    skills = _local_skills(tmp_path, ("one",))
    manifest = _manifest({"agent": skills})
    stage = FakeStage()
    before = build_upload_plan(manifest, tmp_path)[0]
    upload_skills([before], _config(tmp_path), CommandRunner(stage))
    prior_files = dict(stage.files)

    (tmp_path / "skills/library/one/SKILL.md").write_text("# one, revised\n")
    after = build_upload_plan(manifest, tmp_path)[0]
    upload_skills([after], _config(tmp_path), CommandRunner(stage))

    assert after.digest != before.digest
    assert _copy_destination(stage.copies()[-1]) == f"{after.deployed_path}/"
    assert {key: value for key, value in stage.files.items() if key in prior_files} == prior_files


def test_interrupted_upload_is_completed_without_overwriting(tmp_path):
    local = _skill_dir(tmp_path / "skills/library/one", {"SKILL.md": "# one\n", "ref.md": "r\n"})
    plan = build_upload_plan(
        _manifest({"agent": [_skill("one", "@DB.AGENTS.SKILL_STAGE/library/one")]}), tmp_path
    )
    folder = plan[0].deployed_path.split("/", 1)[1]
    data = (local / "SKILL.md").read_bytes()
    stage = FakeStage(
        {
            ("DB.AGENTS.SKILL_STAGE", f"{folder}/SKILL.md"): (
                len(data),
                hashlib.md5(data).hexdigest(),
            )
        }
    )

    outcome = upload_skills(plan, _config(tmp_path), CommandRunner(stage))

    assert [phase.detail for phase in outcome.phases] == ["uploaded"]
    assert "--no-overwrite" in stage.copies()[0]
    assert ("DB.AGENTS.SKILL_STAGE", f"{folder}/ref.md") in stage.files


@pytest.mark.parametrize("damage", ["different", "extra"])
def test_content_folder_with_foreign_files_is_refused_not_overwritten(tmp_path, damage):
    plan = build_upload_plan(_manifest({"agent": _local_skills(tmp_path, ("one",))}), tmp_path)
    folder = plan[0].deployed_path.split("/", 1)[1]
    name = "SKILL.md" if damage == "different" else "unexpected.py"
    stage = FakeStage({("DB.AGENTS.SKILL_STAGE", f"{folder}/{name}"): (3, "0" * 32)})

    with pytest.raises(DurablePhaseError, match="never overwritten"):
        upload_skills(plan, _config(tmp_path), CommandRunner(stage))
    assert stage.copies() == []


def test_upload_that_does_not_read_back_exactly_fails_before_build(tmp_path):
    _skill_dir(tmp_path / "skills/library/one", {"SKILL.md": "# one\n", "ref.md": "r\n"})
    manifest = _manifest({"agent": [_skill("one", "@DB.AGENTS.SKILL_STAGE/library/one")]})
    config = _config(tmp_path)
    plan = build_deploy_plan(manifest, config, ["agent"])
    stage = FakeStage(drop_on_copy={"ref.md"})

    with pytest.raises(DurablePhaseError, match="do not match") as caught:
        apply_deploy_plan(plan, config, runner=CommandRunner(stage))
    assert all(call[1] != "build" for call in stage.calls)
    assert caught.value.outcome.phases[-1].completed is False


def test_deploy_passes_verified_digests_to_dbt(tmp_path):
    skills = _local_skills(tmp_path, ("one", "two"))
    skills[1]["mode"] = "overwrite"
    manifest = _manifest({"agent": skills})
    config = _config(tmp_path)
    plan = build_deploy_plan(manifest, config, ["agent"])
    stage = FakeStage()

    apply_deploy_plan(plan, config, runner=CommandRunner(stage))

    build = stage.calls[-1]
    variables = json.loads(build[build.index("--vars") + 1])
    immutable = next(item for item in plan.skill_uploads if item.mode == "immutable")
    assert variables["cortex_agent_skill_digests"] == {immutable.stage_path: immutable.digest}


def test_overwrite_mode_is_explicit_and_reports_rollback_risk(tmp_path, monkeypatch, capsys):
    skills = _local_skills(tmp_path, ("one",))
    skills[0]["mode"] = "overwrite"
    manifest = _manifest({"agent": skills})
    plan = build_upload_plan(manifest, tmp_path)
    assert plan[0].deployed_path == skills[0]["source"]["path"]
    assert skill_digests(plan) == {}

    stage = FakeStage()
    upload_skills(plan, _config(tmp_path), CommandRunner(stage))
    assert "--overwrite" in stage.copies()[0]
    assert _copy_destination(stage.copies()[0]) == f"{skills[0]['source']['path']}/"

    monkeypatch.setattr("dbt_cortex_agent.commands.skill.fresh_manifest", lambda *a, **k: manifest)
    handle(
        build_parser().parse_args(["skill", "plan", "--agent", "agent", "--json"]),
        _config(tmp_path),
    )
    upload = json.loads(capsys.readouterr().out)["uploads"][0]
    assert upload["mode"] == "overwrite"
    assert upload["rollback_restores_skill_text"] is False
    assert "rolling an Agent back" in upload["warning"]


def test_shared_skill_path_requires_one_mode(tmp_path):
    shared = _local_skills(tmp_path, ("shared",))[0]
    overwrite = {**shared, "mode": "overwrite"}
    with pytest.raises(ValueError, match="one mode"):
        build_upload_plan(_manifest({"agent_a": [shared], "agent_b": [overwrite]}), tmp_path)


@pytest.mark.parametrize(
    "skill",
    [
        {**_skill("one", "@DB.AGENTS.SKILL_STAGE/library/one"), "mode": "versioned"},
        {"name": "one", "source": {"type": "git_integration", "path": GIT_PATH}, "mode": "x"},
        {
            "name": "one",
            "source": {"type": "git_integration", "path": "@DB.AGENTS.REPO/tags/latest/skills/one"},
        },
        {
            "name": "one",
            "source": {"type": "git_integration", "path": "@DB.AGENTS.REPO/commits/abc/o"},
        },
        {
            "name": "one",
            "source": {"type": "git_integration", "path": "@DB.AGENTS.REPO/branches/m/o"},
        },
        {"name": "one", "source": {"type": "git", "path": GIT_PATH}},
    ],
)
def test_invalid_mode_or_unpinned_git_path_fails_planning(tmp_path, skill):
    with pytest.raises(ValueError, match="mode|commit|GIT_INTEGRATION"):
        build_upload_plan(_manifest({"agent": [skill]}), tmp_path)


def test_git_skill_is_smoked_but_never_uploaded(tmp_path):
    upper_sha = GIT_PATH.replace("a" * 40, "A" * 40)
    git_skill = {"name": "one", "source": {"type": "git_integration", "path": upper_sha}}
    manifest = _manifest({"agent": [git_skill]})
    manifest["nodes"]["model.test.agent"]["compiled_code"] = yaml.safe_dump(
        {"skills": [{"name": "one", "source": {"type": "GIT_INTEGRATION", "path": GIT_PATH}}]}
    )

    assert build_upload_plan(manifest, tmp_path) == []
    [declaration] = skill_declarations(manifest, tmp_path)
    assert (declaration.mode, declaration.local_dir) == ("git", None)
    assert declaration.stage_path == GIT_PATH


def test_model_body_mode_is_not_part_of_the_comparison(tmp_path):
    skills = _local_skills(tmp_path, ("one",))
    skills[0]["mode"] = "overwrite"
    manifest = _manifest({"agent": skills})
    body = [{"name": "one", "source": {"type": "STAGE", "path": skills[0]["source"]["path"]}}]
    manifest["nodes"]["model.test.agent"]["compiled_code"] = yaml.safe_dump({"skills": body})
    assert build_upload_plan(manifest, tmp_path)[0].mode == "overwrite"


def test_deploy_commits_the_verified_folder_through_the_real_materialization(
    tmp_path, macro_harness
):
    from types import SimpleNamespace

    skills = _local_skills(tmp_path, ("one",))
    manifest = _manifest({"agent": skills})
    config = _config(tmp_path)
    plan = build_deploy_plan(manifest, config, ["agent"])
    stage = FakeStage()
    deployed = []
    macro_harness.context.update(
        this=SimpleNamespace(database="DB", schema="AGENTS", identifier="AGENT"),
        model=SimpleNamespace(name="agent", unique_id="model.test.agent"),
        config={"meta": {"cortex_agent": {"skills": skills}}},
        target=SimpleNamespace(name="sandbox"),
        sql=yaml.safe_dump({"models": {"orchestration": "auto"}, "skills": skills}),
        pre_hooks=[],
        post_hooks=[],
        run_hooks=lambda *args, **kwargs: "",
        statement=lambda name, caller: "",
    )
    macro_harness.override("cortex_agent__assert_staged_skills_ready", lambda spec: None)
    macro_harness.override("cortex_agent__skills_hash", lambda spec: "")
    macro_harness.override("cortex_agent__apply_deploy", lambda *args: deployed.append(args))

    def run(command, **kwargs):
        if command[1] != "build":
            return stage(command, **kwargs)
        variables = json.loads(command[command.index("--vars") + 1])
        variables.update(
            cortex_agent_allowed_targets=["sandbox"], cortex_agent_allowed_databases=["DB"]
        )
        macro_harness.context["var"] = lambda name, default=None: variables.get(name, default)
        macro_harness.call("materialization_cortex_agent")
        return subprocess.CompletedProcess(command, 0, _reconciled_output("DB.AGENTS.AGENT"), "")

    apply_deploy_plan(plan, config, runner=CommandRunner(run))

    spec = json.loads(deployed[0][1])
    assert spec["skills"][0]["source"]["path"] == plan.skill_uploads[0].deployed_path
    assert (
        "DB.AGENTS.SKILL_STAGE",
        plan.skill_uploads[0].deployed_path.split("/", 1)[1] + "/SKILL.md",
    ) in stage.files
