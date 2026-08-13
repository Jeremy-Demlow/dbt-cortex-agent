from __future__ import annotations

import json
import re
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.deploy import (
    RENDER_MARKER,
    _parse_render_output,
    deploy_agents,
    lifecycle_macro,
    render_agents,
)


def _project(tmp_path, *, include_skill=True, manifest=None):
    skill = {
        "name": "shared",
        "source": {"type": "stage", "path": "@DB.AGENTS.SKILL_STAGE/library/shared"},
    }
    default_manifest = {
        "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
        "nodes": {
            "model.test.anchor": {
                "name": "anchor",
                "resource_type": "model",
                "database": "DB",
                "schema": "ANALYTICS",
            }
        },
        "exposures": {
            "exposure.test.agent": {
                "name": "agent",
                "meta": {
                    "cortex_agent": {
                        "enabled": True,
                        "capabilities": {"skills": [skill] if include_skill else []},
                    }
                },
            }
        },
    }
    manifest = manifest or default_manifest
    target = tmp_path / "target"
    target.mkdir()
    (target / "manifest.json").write_text(json.dumps(manifest))
    if include_skill:
        directory = tmp_path / "skills/library/shared"
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text("# Shared\n")


def _config(tmp_path):
    return resolve_config(
        Namespace(
            project_dir=str(tmp_path),
            manifest=None,
            target="sandbox",
            connection="conn",
            database="DB",
            schema="AGENTS",
            role=None,
            warehouse=None,
            artifact_dir=None,
            dbt_executable="dbt-custom",
            snow_executable="snow-custom",
        ),
        env={},
    )


class FakeRunner:
    def __init__(self, fail_on=None):
        self.calls = []
        self.kwargs = []
        self.fail_on = fail_on

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        self.kwargs.append(kwargs)
        failed = self.fail_on and self.fail_on(command)
        stdout = ""
        if not failed and len(command) > 2 and command[2] in {
            "cortex_agent__render_spec",
            "cortex_agent__deploy",
        }:
            arguments = _macro_args(command)
            payload = {
                "agent": arguments["agent_name"],
                "physical_agent": "DB.AGENTS.AGENT",
                "lifecycle_contract": "single_agent",
                "spec": {"tools": []},
                "target": "sandbox",
            }
            stdout = f"12:00:00  {RENDER_MARKER}{json.dumps(payload)}\n"
        return subprocess.CompletedProcess(
            command, 1 if failed else 0, stdout, "failed" if failed else ""
        )


def _macro_args(command):
    return json.loads(command[command.index("--args") + 1])


def test_dry_run_deploy_invokes_only_canonical_macro(tmp_path):
    _project(tmp_path)
    fake = FakeRunner()

    deploy_agents(
        _config(tmp_path),
        ["agent"],
        apply=False,
        allowed_targets=[],
        allowed_databases=[],
        runner=CommandRunner(fake),
    )

    assert len(fake.calls) == 1
    assert fake.calls[0][:3] == ["dbt-custom", "run-operation", "cortex_agent__deploy"]
    assert _macro_args(fake.calls[0]) == {"agent_name": "agent", "dry_run": True}


def test_deploy_passes_resolved_environment_to_dbt_macro(tmp_path):
    _project(tmp_path, include_skill=False)
    fake = FakeRunner()
    config = _config(tmp_path)
    context = type("Context", (), {"dbt_env": {"SNOWFLAKE_ACCOUNT": "acct"}})()
    config = __import__("dataclasses").replace(config, execution_context=context)

    deploy_agents(
        config,
        ["agent"],
        apply=False,
        allowed_targets=[],
        allowed_databases=[],
        runner=CommandRunner(fake),
    )

    assert fake.kwargs[0]["env"] == {"SNOWFLAKE_ACCOUNT": "acct"}


def test_deploy_always_uploads_skills_after_apply_preflight(tmp_path):
    _project(tmp_path)
    fake = FakeRunner()

    result = deploy_agents(
        _config(tmp_path),
        ["agent"],
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        runner=CommandRunner(fake),
    )

    assert fake.calls[0][2] == "cortex_agent__validate_deploy_context"
    assert fake.calls[-1][2] == "cortex_agent__deploy"
    assert any(call[0:3] == ["snow-custom", "stage", "copy"] for call in fake.calls)
    assert result.renders[0]["physical_agent"] == "DB.AGENTS.AGENT"


def test_plan_failure_causes_zero_subprocess_calls(tmp_path):
    _project(tmp_path)
    (tmp_path / "skills/library/shared/SKILL.md").unlink()
    fake = FakeRunner()

    with pytest.raises(FileNotFoundError):
        deploy_agents(
            _config(tmp_path),
            ["agent"],
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            runner=CommandRunner(fake),
        )

    assert fake.calls == []


def test_context_preflight_failure_prevents_upload_and_deploy(tmp_path):
    _project(tmp_path)
    fake = FakeRunner(
        lambda command: "cortex_agent__validate_deploy_context" in command
    )

    with pytest.raises(RuntimeError, match="failed"):
        deploy_agents(
            _config(tmp_path),
            ["agent"],
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            runner=CommandRunner(fake),
        )

    assert len(fake.calls) == 1
    assert "cortex_agent__validate_deploy_context" in fake.calls[0]


def test_upload_failure_prevents_canonical_agent_macro(tmp_path):
    _project(tmp_path)
    fake = FakeRunner(lambda command: command[:3] == ["snow-custom", "stage", "copy"])

    with pytest.raises(RuntimeError, match="failed"):
        deploy_agents(
            _config(tmp_path),
            ["agent"],
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            runner=CommandRunner(fake),
        )

    assert fake.calls[0][1:3] == ["run-operation", "cortex_agent__validate_deploy_context"]
    assert [call[1:3] for call in fake.calls[1:]] == [
        ["sql", "--connection"],
        ["stage", "copy"],
    ]
    assert not any("cortex_agent__deploy" in call for call in fake.calls)


def test_success_uploads_all_before_canonical_agent_macro(tmp_path):
    _project(tmp_path)
    fake = FakeRunner()

    deploy_agents(
        _config(tmp_path),
        ["agent"],
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        runner=CommandRunner(fake),
    )

    assert fake.calls[0][1:3] == ["run-operation", "cortex_agent__validate_deploy_context"]
    assert fake.calls[-1][1:3] == ["run-operation", "cortex_agent__deploy"]
    assert _macro_args(fake.calls[-1])["dry_run"] is False
    assert all("cortex_agent__deploy" not in call for call in fake.calls[:-1])
    variables = json.loads(fake.calls[-1][fake.calls[-1].index("--vars") + 1])
    assert variables == {
        "cortex_agent_allowed_databases": ["DB"],
        "cortex_agent_allowed_targets": ["sandbox"],
    }


def test_render_and_lifecycle_commands_delegate_with_expected_args(tmp_path):
    _project(tmp_path, include_skill=False)
    fake = FakeRunner()
    runner = CommandRunner(fake)

    render_agents(_config(tmp_path), ["agent"], runner)
    lifecycle_macro(
        _config(tmp_path),
        ["agent"],
        "cortex_agent__promote_alias",
        {"from_alias": "validated", "to_alias": "production"},
        apply=False,
        allowed_targets=[],
        allowed_databases=[],
        runner=runner,
    )

    assert fake.calls[0][2] == "cortex_agent__render_spec"
    assert _macro_args(fake.calls[0]) == {"agent_name": "agent"}
    assert fake.calls[1][2] == "cortex_agent__promote_alias"
    assert _macro_args(fake.calls[1])["dry_run"] is True


def test_render_exposes_full_spec_and_writes_stable_contained_artifact(tmp_path):
    _project(tmp_path, include_skill=False)
    fake = FakeRunner()

    result = render_agents(
        _config(tmp_path),
        ["agent"],
        CommandRunner(fake),
    )

    render = result.renders[0]
    artifact = Path(render["artifact"])
    assert render == {
        "agent": "agent",
        "artifact": str(
            tmp_path
            / "target/dbt_cortex_agent/renders/sandbox/agent/spec.json"
        ),
        "physical_agent": "DB.AGENTS.AGENT",
        "lifecycle_contract": "single_agent",
        "spec": {"tools": []},
        "target": "sandbox",
    }
    assert json.loads(artifact.read_text()) == render["spec"]
    assert _macro_args(fake.calls[0]) == {"agent_name": "agent"}


@pytest.mark.parametrize(
    ("stdout", "message"),
    [
        ("", "found 0"),
        (
            f'{RENDER_MARKER}{{"agent":"agent"}}\n{RENDER_MARKER}{{"agent":"agent"}}',
            "found 2",
        ),
        (f"{RENDER_MARKER}{{", "Malformed render marker JSON"),
        (f"{RENDER_MARKER}[]", "must contain a JSON object"),
        (
            f'{RENDER_MARKER}{{"agent":"agent","lifecycle_contract":"single_agent",'
            '"target":"sandbox","physical_agent":"DB.S.A","spec":[]}',
            "spec for Agent 'agent' must be a JSON object",
        ),
    ],
)
def test_render_marker_parser_fails_closed(stdout, message):
    with pytest.raises(ValueError, match=message):
        _parse_render_output(stdout, "agent")


def test_macro_single_agent_marker_contract():
    root = Path(__file__).parents[1]
    contract = (root / "macros/cortex_agents/agent_contract.sql").read_text()
    render = (root / "macros/cortex_agents/agent_render.sql").read_text()

    assert "validate_projection" not in contract
    assert "cortex_agent_eval_suffix" not in render
    assert "lifecycle_contract" in render
    assert "{% do log(tojson(spec), info=True) %}" in render
    assert render.count("__DBT_CORTEX_AGENT_RENDER__=") == 2


def test_public_agent_macros_have_no_projection_interface():
    root = Path(__file__).parents[1] / "macros/cortex_agents"
    sources = {
        name: (root / name).read_text(encoding="utf-8")
        for name in (
            "agent_contract.sql",
            "agent_render.sql",
            "agent_grants.sql",
            "agent_versioning.sql",
        )
    }

    for source in sources.values():
        assert "projection=" not in source
        assert "cortex_agent_eval_suffix" not in source
        assert "native_eval" not in source
    assert "{% macro cortex_agent__render_spec(agent_name) %}" in sources["agent_render.sql"]
    assert "{% macro cortex_agent__deploy(agent_name, dry_run=True, alias=None) %}" in sources["agent_render.sql"]
    assert "{% macro cortex_agent__grant_usage(agent_name, dry_run=True) %}" in sources["agent_grants.sql"]
    assert "GRANT MONITOR ON AGENT" in sources["agent_grants.sql"]
    assert "monitor_roles" in sources["agent_grants.sql"]
    assert 'statements.append("GRANT USAGE ON AGENT "' in sources["agent_grants.sql"]
    assert 'statements.append("GRANT MONITOR ON AGENT "' in sources["agent_grants.sql"]
    assert 'statements.append("GRANT USAGE ON CORTEX SEARCH SERVICE "' in sources["agent_grants.sql"]
    assert "tool.get('access', {}).get('usage_roles', [])" in sources["agent_grants.sql"]
    assert "cortex_agent__unquoted_fqn" in sources["agent_grants.sql"]
    assert "{% macro cortex_agent__set_alias(agent_name, alias, to_version=none, from_alias=none, dry_run=true) %}" in sources["agent_versioning.sql"]


def test_eval_macros_target_single_agent_without_deploying_it():
    root = Path(__file__).parents[1] / "macros/cortex_agents"
    render = (root / "eval_render.sql").read_text(encoding="utf-8")
    run = (root / "eval_run.sql").read_text(encoding="utf-8")

    assert "cortex_agent__resource_agent_fqn(resource, agent)" in render
    assert "projection" not in render
    assert "cortex_agent__resource_agent_fqn(resource, agent)" in run
    for forbidden in ("cortex_agent__deploy", "cortex_agent__build(", "CREATE AGENT", "ALTER AGENT"):
        assert forbidden not in render + run


@pytest.mark.parametrize(
    ("macro", "arguments"),
    [
        ("cortex_agent__grant_usage", {}),
        (
            "cortex_agent__promote_alias",
            {"from_alias": "validated", "to_alias": "production"},
        ),
        (
            "cortex_agent__rollback_alias",
            {"alias": "production", "to_version": "VERSION$2"},
        ),
    ],
)
def test_python_lifecycle_operations_delegate_to_dbt_macros(tmp_path, macro, arguments):
    _project(tmp_path, include_skill=False)
    fake = FakeRunner()

    lifecycle_macro(
        _config(tmp_path),
        ["agent"],
        macro,
        arguments,
        apply=False,
        allowed_targets=[],
        allowed_databases=[],
        runner=CommandRunner(fake),
    )

    assert len(fake.calls) == 1
    assert fake.calls[0][:3] == ["dbt-custom", "run-operation", macro]
    assert _macro_args(fake.calls[0]) == {
        "agent_name": "agent",
        **arguments,
        "dry_run": True,
    }


def test_python_source_contains_no_mutating_agent_ddl():
    source_root = Path(__file__).parents[1] / "src" / "dbt_cortex_agent"
    mutating_agent_ddl = re.compile(
        r"\b(?:CREATE(?:\s+OR\s+REPLACE)?|ALTER|DROP)\s+AGENT\b", re.IGNORECASE
    )

    offenders = [
        str(path.relative_to(source_root))
        for path in source_root.rglob("*.py")
        if mutating_agent_ddl.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def test_cortex_agent_materialization_reuses_immutable_lifecycle():
    materialization = (
        Path(__file__).parents[1]
        / "macros/materializations/cortex_agent.sql"
    ).read_text(encoding="utf-8")

    assert "{% materialization cortex_agent, adapter='snowflake' %}" in materialization
    assert "cortex_agent__apply_deploy" in materialization
    assert "{% call statement('main') %}" in materialization
    assert "dbt_cortex_agent.cortex_agent__apply_deploy" in materialization
    assert "{% do cortex_agent__apply_deploy" not in materialization
    assert "cortex_agent__assert_staged_skills_ready(spec)" in materialization
    assert "cortex_agent__skills_hash(spec)" in materialization
    assert "CREATE AGENT" not in materialization
    assert "MODIFY LIVE VERSION" not in materialization
    assert "COMMIT" not in materialization
    assert "return({'relations': []})" in materialization
    assert "run_hooks(pre_hooks, inside_transaction=False)" in materialization
    assert "run_hooks(post_hooks, inside_transaction=False)" in materialization
    assert "USE ROLE {{ safe_agent_role }}" in materialization
    assert "USE ROLE {{ safe_original_role }}" in materialization

    render = (
        Path(__file__).parents[1] / "macros/cortex_agents/agent_render.sql"
    ).read_text(encoding="utf-8")
    assert render.count(
        "agent.get('skills', agent.get('capabilities', {}).get('skills', []))"
    ) == 2


def test_cortex_agent_materialization_requires_explicit_orchestration():
    materialization = (
        Path(__file__).parents[1]
        / "macros/materializations/cortex_agent.sql"
    ).read_text(encoding="utf-8")

    assert "must explicitly define models.orchestration" in materialization
    assert "cortex_agent_default_model" not in materialization
    assert "claude-sonnet-4-6" not in materialization
    assert "'$'" not in materialization


def test_model_agents_fail_closed_from_legacy_render_deploy_cli(tmp_path):
    manifest = {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"
        },
        "exposures": {},
        "nodes": {
            "model.consumer.agent": {
                "unique_id": "model.consumer.agent",
                "resource_type": "model",
                "name": "agent",
                "database": "DB",
                "schema": "AGENTS",
                "alias": "AGENT",
                "config": {"materialized": "cortex_agent"},
            }
        },
    }
    _project(tmp_path, include_skill=False, manifest=manifest)

    with pytest.raises(ValueError, match="use dbt build --select agent"):
        render_agents(_config(tmp_path), ["agent"], CommandRunner(FakeRunner()))
    with pytest.raises(ValueError, match="use dbt build --select agent"):
        deploy_agents(
            _config(tmp_path),
            ["agent"],
            apply=False,
            allowed_targets=[],
            allowed_databases=[],
            runner=CommandRunner(FakeRunner()),
        )


def test_legacy_exposure_contract_also_requires_explicit_orchestration():
    root = Path(__file__).parents[1]
    contract = (root / "macros/cortex_agents/agent_contract.sql").read_text(
        encoding="utf-8"
    )
    render = (root / "macros/cortex_agents/agent_render.sql").read_text(
        encoding="utf-8"
    )

    assert "must explicitly define model.orchestration" in contract
    assert "cortex_agent_default_model" not in render
    assert "claude-sonnet-4-5" not in render


def test_no_change_deploy_reconciles_only_explicit_alias_without_commit():
    macro = (
        Path(__file__).parents[1] / "macros/cortex_agents/agent_render.sql"
    ).read_text(encoding="utf-8")
    no_change = macro[macro.index("current_hashes.get('spec_md5')") : macro.index(
        "{% if not existed %}"
    )]

    assert "reconcile_alias and default_version" in no_change
    assert "MODIFY VERSION " in no_change and " SET ALIAS = " in no_change
    assert 'run_query("ALTER AGENT " ~ agent_fqn ~ " COMMIT")' not in no_change


def test_grant_macro_validates_roles_as_unquoted_identifiers():
    macro = (
        Path(__file__).parents[1] / "macros/cortex_agents/agent_grants.sql"
    ).read_text(encoding="utf-8")

    assert "cortex_agent__unquoted_identifier(role, 'usage role')" in macro
    assert 'TO ROLE " ~ safe_role' in macro


def test_search_tool_access_is_strict_and_exact_object_only():
    root = Path(__file__).parents[1] / "macros/cortex_agents"
    contract = (root / "agent_contract.sql").read_text(encoding="utf-8")
    grants = (root / "agent_grants.sql").read_text(encoding="utf-8")
    render = (root / "agent_render.sql").read_text(encoding="utf-8")

    assert "parts | length != 3" in render
    assert "cortex_agent__unquoted_identifier(part, label ~ ' part')" in render
    assert "access.usage_roles must be a list" in contract
    assert 'GRANT USAGE ON CORTEX SEARCH SERVICE " ~ search_fqn' in grants
    assert "FUTURE CORTEX SEARCH" not in grants
    assert "ALL CORTEX SEARCH" not in grants
