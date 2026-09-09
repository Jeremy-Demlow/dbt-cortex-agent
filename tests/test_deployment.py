from __future__ import annotations

import subprocess

import pytest

# Evidence: TC-022-01 TC-022-05 TC-023-08 TC-030-03 TC-030-04
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.deployment import (
    _dbt_phases,
    apply_deploy_plan,
    build_deploy_plan,
    validate_deploy_plan,
)
from dbt_cortex_agent.domain import DurablePhaseError, LifecyclePhase, OperationOutcome


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
                "unique_id": "model.x.agent_a",
                "resource_type": "model",
                "name": "agent_a",
                "database": "DB_A",
                "schema": "AGENTS",
                "alias": "SHARED",
                "config": {"materialized": "cortex_agent", "meta": {}},
            },
            "model.x.agent_b": {
                "unique_id": "model.x.agent_b",
                "resource_type": "model",
                "name": "agent_b",
                "database": "DB_B",
                "schema": "AGENTS",
                "alias": "SHARED",
                "config": {"materialized": "cortex_agent", "meta": {}},
            },
            "model.x.upstream": {
                "unique_id": "model.x.upstream",
                "resource_type": "model",
                "name": "upstream",
                "database": "DATA_DB",
                "schema": "MART",
                "alias": "UPSTREAM",
                "config": {"materialized": "table"},
            },
        },
        "parent_map": {
            "model.x.agent_a": ["model.x.upstream"],
            "model.x.agent_b": [],
            "model.x.upstream": [],
        },
    }


def test_deploy_plan_keeps_physical_identity_and_dependency_selection(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a", "agent_b"])

    assert [item["physical_fqn"] for item in plan.agents] == [
        "DB_A.AGENTS.SHARED",
        "DB_B.AGENTS.SHARED",
    ]
    assert plan.dbt_selection == ("+agent_a", "+agent_b")
    assert plan.resource_databases == ("DATA_DB", "DB_A", "DB_B")


def test_deploy_plan_requires_complete_resource_allowlist(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a", "agent_b"])

    with pytest.raises(ValueError, match="DB_B"):
        validate_deploy_plan(plan, _config(tmp_path), ["sandbox"], ["DB_A", "DATA_DB"])


def test_connection_database_does_not_narrow_multi_database_resource_scope(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a", "agent_b"])

    validate_deploy_plan(
        plan,
        _config(tmp_path),
        ["sandbox"],
        ["DB_A", "DB_B", "DATA_DB"],
    )


def test_deploy_plan_requires_dependency_database_allowlist(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])

    with pytest.raises(ValueError, match="DATA_DB"):
        validate_deploy_plan(plan, _config(tmp_path), ["sandbox"], ["DB_A"])


def test_apply_runs_dbt_build_after_skill_phase(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    outcome = apply_deploy_plan(plan, _config(tmp_path), runner=CommandRunner(run))

    assert calls == [
        [
            "dbt",
            "build",
            "--project-dir",
            str(tmp_path),
            "--target",
            "sandbox",
            "--select",
            "+agent_a",
        ]
    ]
    assert [item["phase"] for item in outcome.to_dict()] == [
        "preflight",
        "skills_uploaded",
        "verified",
    ]


def test_dbt_failure_reports_reconciliation_as_indeterminate(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])

    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "dbt failed", "")

    with pytest.raises(DurablePhaseError) as exc:
        apply_deploy_plan(plan, _config(tmp_path), runner=CommandRunner(run))

    failed = exc.value.outcome.phases[-1]
    assert failed.phase is LifecyclePhase.VERIFIED
    assert failed.completed is False
    assert "indeterminate" in str(failed.detail)


def test_dbt_phase_markers_are_deduplicated_and_unknown_markers_ignored():
    output = """CORTEX_AGENT_DEPLOY_PHASE=version_committed
CORTEX_AGENT_DEPLOY_PHASE=version_committed
CORTEX_AGENT_DEPLOY_PHASE=future_phase
CORTEX_AGENT_DEPLOY_PHASE=metadata_reconciled
"""

    outcome = _dbt_phases(output, OperationOutcome())

    assert [item.phase for item in outcome.phases] == [
        LifecyclePhase.VERSION_COMMITTED,
        LifecyclePhase.METADATA_RECONCILED,
    ]


def test_dbt_failure_preserves_markers_from_stdout_and_stderr(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])

    def run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            1,
            "CORTEX_AGENT_DEPLOY_PHASE=version_committed",  # pragma: allowlist secret
            "CORTEX_AGENT_DEPLOY_PHASE=metadata_reconciled\ndbt failed",
        )

    with pytest.raises(DurablePhaseError) as exc:
        apply_deploy_plan(plan, _config(tmp_path), runner=CommandRunner(run))

    assert [item.phase for item in exc.value.outcome.phases] == [
        LifecyclePhase.PREFLIGHT,
        LifecyclePhase.SKILLS_UPLOADED,
        LifecyclePhase.VERSION_COMMITTED,
        LifecyclePhase.METADATA_RECONCILED,
        LifecyclePhase.VERIFIED,
    ]


def test_skill_upload_programming_error_is_not_reported_as_durable_failure(
    monkeypatch, tmp_path
) -> None:
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])
    monkeypatch.setattr(
        "dbt_cortex_agent.deployment.upload_skills",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("programming defect")),
    )

    with pytest.raises(AssertionError, match="programming defect"):
        apply_deploy_plan(plan, _config(tmp_path))
