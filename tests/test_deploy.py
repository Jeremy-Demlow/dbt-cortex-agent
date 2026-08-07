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


def _project(tmp_path, *, include_skill=True):
    skill = {
        "name": "shared",
        "source": {"type": "stage", "path": "@DB.AGENTS.SKILL_STAGE/library/shared"},
    }
    manifest = {
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
        self.fail_on = fail_on

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        failed = self.fail_on and self.fail_on(command)
        stdout = ""
        if not failed and len(command) > 2 and command[2] in {
            "cortex_agent__render_spec",
            "cortex_agent__deploy",
        }:
            arguments = _macro_args(command)
            payload = {
                "agent": arguments["agent_name"],
                "physical_agent": (
                    "DB.AGENTS.AGENT_EVAL"
                    if arguments["projection"] == "native_eval"
                    else "DB.AGENTS.AGENT"
                ),
                "projection": arguments["projection"],
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
    assert _macro_args(fake.calls[0]) == {
        "agent_name": "agent",
        "dry_run": True,
        "projection": "canonical",
    }


def test_native_eval_deploy_skips_skill_plan_and_upload_but_keeps_apply_preflight(
    tmp_path, monkeypatch
):
    _project(tmp_path)
    fake = FakeRunner()
    monkeypatch.setattr(
        "dbt_cortex_agent.deploy.build_upload_plan",
        lambda *args: pytest.fail("native_eval deploy planned skills"),
    )

    result = deploy_agents(
        _config(tmp_path),
        ["agent"],
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        projection="native_eval",
        runner=CommandRunner(fake),
    )

    assert fake.calls[0][2] == "cortex_agent__validate_deploy_context"
    assert fake.calls[-1][2] == "cortex_agent__deploy"
    assert _macro_args(fake.calls[-1])["projection"] == "native_eval"
    assert not any(call[0:3] == ["snow-custom", "stage", "copy"] for call in fake.calls)
    assert result.renders[0]["physical_agent"] == "DB.AGENTS.AGENT_EVAL"


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
    assert _macro_args(fake.calls[0])["projection"] == "canonical"
    assert fake.calls[1][2] == "cortex_agent__promote_alias"
    assert _macro_args(fake.calls[1])["dry_run"] is True


def test_render_native_eval_exposes_spec_and_writes_deterministic_contained_artifact(tmp_path):
    _project(tmp_path, include_skill=False)
    fake = FakeRunner()

    result = render_agents(
        _config(tmp_path),
        ["agent"],
        CommandRunner(fake),
        projection="native_eval",
    )

    render = result.renders[0]
    artifact = Path(render["artifact"])
    assert render == {
        "agent": "agent",
        "artifact": str(
            tmp_path
            / "target/dbt_cortex_agent/renders/sandbox/agent/native_eval.json"
        ),
        "physical_agent": "DB.AGENTS.AGENT_EVAL",
        "projection": "native_eval",
        "spec": {"tools": []},
        "target": "sandbox",
    }
    assert json.loads(artifact.read_text()) == render["spec"]
    assert _macro_args(fake.calls[0])["projection"] == "native_eval"


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
            f'{RENDER_MARKER}{{"agent":"agent","projection":"canonical",'
            '"target":"sandbox","physical_agent":"DB.S.A","spec":[]}',
            "spec for Agent 'agent' must be a JSON object",
        ),
    ],
)
def test_render_marker_parser_fails_closed(stdout, message):
    with pytest.raises(ValueError, match=message):
        _parse_render_output(stdout, "agent", "canonical")


def test_macro_projection_validation_and_marker_contract():
    root = Path(__file__).parents[1]
    contract = (root / "macros/cortex_agents/agent_contract.sql").read_text()
    render = (root / "macros/cortex_agents/agent_render.sql").read_text()

    assert "projection not in ['canonical', 'native_eval']" in contract
    assert "{% do cortex_agent__validate_projection(projection) %}" in contract
    assert "{% do log(tojson(spec), info=True) %}" in render
    assert render.count("__DBT_CORTEX_AGENT_RENDER__=") == 2


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
