from __future__ import annotations

import subprocess

import pytest

from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.deployment import apply_deploy_plan, build_deploy_plan, validate_deploy_plan


def _config(tmp_path):
    class Args:
        project_dir = str(tmp_path)
        manifest = None
        target = "sandbox"
        connection = "named"
        database = "DB_A"
        schema = None
        role = "ROLE"
        warehouse = "WH"
        artifact_dir = None
        dbt_executable = "dbt"
        snow_executable = "snow"

    return resolve_config(Args(), {})


def _manifest():
    return {
        "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
        "nodes": {
            "model.x.agent_a": {
                "unique_id": "model.x.agent_a", "resource_type": "model", "name": "agent_a",
                "database": "DB_A", "schema": "AGENTS", "alias": "SHARED",
                "config": {"materialized": "cortex_agent", "meta": {}},
            },
            "model.x.agent_b": {
                "unique_id": "model.x.agent_b", "resource_type": "model", "name": "agent_b",
                "database": "DB_B", "schema": "AGENTS", "alias": "SHARED",
                "config": {"materialized": "cortex_agent", "meta": {}},
            },
        },
    }


def test_deploy_plan_keeps_physical_identity_and_dependency_selection(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a", "agent_b"])

    assert [item["physical_fqn"] for item in plan.agents] == [
        "DB_A.AGENTS.SHARED", "DB_B.AGENTS.SHARED"
    ]
    assert plan.dbt_selection == ("+agent_a", "+agent_b")


def test_deploy_plan_requires_complete_resource_allowlist(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a", "agent_b"])

    with pytest.raises(ValueError, match="DB_B"):
        validate_deploy_plan(plan, _config(tmp_path), ["sandbox"], ["DB_A"])


def test_apply_runs_dbt_build_after_skill_phase(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    apply_deploy_plan(plan, _config(tmp_path), runner=CommandRunner(run))

    assert calls == [["dbt", "build", "--project-dir", str(tmp_path), "--target", "sandbox", "--select", "+agent_a"]]