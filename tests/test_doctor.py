from __future__ import annotations

import json
import subprocess
from argparse import Namespace

from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.doctor import run_doctor


def _manifest():
    return {
        "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
        "exposures": {
            "exposure.p.agent": {
                "name": "agent", "meta": {"cortex_agent": {"enabled": True}}
            }
        },
        "nodes": {
            "model.p.eval": {
                "name": "eval", "database": "DB", "schema": "EVAL", "alias": "EVAL",
                "meta": {"cortex_eval": {"enabled": True}},
            }
        },
    }


def _config(tmp_path, connection=None):
    (tmp_path / "dbt_project.yml").write_text(
        "name: consumer\nversion: 1.0.0\nconfig-version: 2\nvars:\n"
        "  cortex_agent_deploy_target: sandbox\n"
        "  cortex_agent_allowed_targets: [sandbox]\n"
        "  cortex_agent_allowed_databases: [DB]\n"
    )
    manifest = tmp_path / "target/manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps(_manifest()))
    return resolve_config(
        Namespace(
            project_dir=str(tmp_path), manifest=str(manifest), target="dev",
            connection=connection, database=None, schema=None, role=None, warehouse=None,
            artifact_dir=None, dbt_executable="dbt-custom", snow_executable="snow-custom",
        ),
        env={},
    )


def test_doctor_runs_only_version_checks_without_connection(tmp_path):
    config = _config(tmp_path)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "version output", "")

    diagnostics = run_doctor(config, CommandRunner(fake_run))

    assert commands == [["dbt-custom", "--version"], ["snow-custom", "--version"]]
    assert next(item for item in diagnostics if item.name == "Snowflake connection").status == "SKIP"
    assert next(item for item in diagnostics if item.name == "enabled Agents").detail == "agent"
    assert next(item for item in diagnostics if item.name == "enabled evals").detail == "eval"
    assert next(item for item in diagnostics if item.name == "deployment safety").status == "PASS"


def test_doctor_connection_check_is_explicit_and_read_only(tmp_path):
    config = _config(tmp_path, connection="named")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    run_doctor(config, CommandRunner(fake_run))

    assert commands[-1] == ["snow-custom", "connection", "test", "--connection", "named"]
    joined = " ".join(" ".join(command).lower() for command in commands)
    for forbidden in ("agent", "evaluation", "upload", "put", "create", "alter", "drop"):
        assert forbidden not in joined


def test_doctor_does_not_connect_for_environment_only_connection(tmp_path):
    config = _config(tmp_path)
    object.__setattr__(config, "connection", "from-environment")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    diagnostics = run_doctor(config, CommandRunner(fake_run))

    assert commands == [["dbt-custom", "--version"], ["snow-custom", "--version"]]
    assert next(item for item in diagnostics if item.name == "Snowflake connection").status == "SKIP"


def test_doctor_fails_closed_on_manifest_and_safety_errors(tmp_path):
    config = _config(tmp_path)
    config.manifest.write_text("{}")
    (tmp_path / "dbt_project.yml").write_text("name: consumer\nversion: 1.0.0\nconfig-version: 2\n")

    diagnostics = run_doctor(
        config,
        CommandRunner(lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "ok", "")),
    )

    assert next(item for item in diagnostics if item.name == "manifest v12").status == "FAIL"
    safety = next(item for item in diagnostics if item.name == "deployment safety")
    assert safety.status == "FAIL"
    assert "--target and --allow-database" in safety.detail


def test_doctor_explains_missing_active_target(tmp_path):
    config = _config(tmp_path)
    object.__setattr__(config, "target", None)

    diagnostics = run_doctor(
        config,
        CommandRunner(lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "ok", "")),
    )

    safety = next(item for item in diagnostics if item.name == "deployment safety")
    assert safety.status == "WARN"
    assert "supply --target" in safety.detail


def test_doctor_detects_consumer_version_mismatch(tmp_path):
    config = _config(tmp_path)
    (tmp_path / "packages.yml").write_text(
        "packages:\n  - git: https://github.com/Jeremy-Demlow/dbt-cortex-agent.git\n"
        "    revision: v0.1.0\n"
    )

    diagnostics = run_doctor(
        config,
        CommandRunner(lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "ok", "")),
    )

    check = next(item for item in diagnostics if item.name == "consumer package version")
    assert check.status == "FAIL"
    assert "0.1.0" in check.detail