from __future__ import annotations

import json
import re
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.deploy import deploy_agents, lifecycle_macro, render_agents


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
        return subprocess.CompletedProcess(command, 1 if failed else 0, "", "failed" if failed else "")


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
