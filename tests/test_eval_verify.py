from __future__ import annotations

import subprocess
import json
from types import SimpleNamespace

import pytest

from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.eval.verify import VerifySelection, build_verify_selections, verify_evaluations


def _config(tmp_path):
    args = SimpleNamespace(
        project_dir=str(tmp_path), manifest=None, target="sandbox",
        connection="named", database="DB", schema=None, role="ROLE",
        warehouse="WH", artifact_dir=None, dbt_executable="dbt", snow_executable="snow",
    )
    return resolve_config(args, {})


def _plan(suite="core"):
    return SimpleNamespace(
        agent_name="agent", suite_name=suite, agent_fqn="DB.AGENTS.AGENT",
        eval_model=f"agent_{suite}", target_name="sandbox", plan_signature=f"signature-{suite}",
    )


def test_verify_preview_is_deterministic_and_non_mutating(tmp_path):
    selections = (
        VerifySelection(_plan("safety"), tmp_path / "safety.json"),
        VerifySelection(_plan("core"), tmp_path / "core.json"),
    )

    result = verify_evaluations(
        _config(tmp_path), selections, apply=False,
        allowed_targets=[], allowed_databases=[], poll_attempts=1,
        poll_interval=0, transient_retries=0,
    )

    assert result["outcome"] == "planned"
    assert result["passed"] is None
    assert [item["suite"] for item in result["suites"]] == ["safety", "core"]


def test_duplicate_suite_selection_fails_before_plan(tmp_path):
    with pytest.raises(ValueError, match="unique"):
        build_verify_selections(_config(tmp_path), "agent", ["core", "core"], tmp_path, parse=False)


def test_eval_model_failure_is_infrastructure_error(tmp_path):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1, "", "dbt failed")

    with pytest.raises(RuntimeError, match="dbt failed"):
        verify_evaluations(
            _config(tmp_path), (VerifySelection(_plan(), tmp_path / "baseline.json"),),
            apply=True, allowed_targets=["sandbox"], allowed_databases=["DB"],
            poll_attempts=1, poll_interval=0, transient_retries=0,
            runner=CommandRunner(run),
        )

    assert calls[0][:2] == ["dbt", "build"]


def test_missing_baseline_uses_intrinsic_candidate_result(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate.json"
    identity = {
        "target_name": "sandbox", "agent_name": "agent", "suite_name": "core",
        "eval_model": "agent_core", "agent_fqn": "DB.AGENTS.AGENT",
        "dataset_fqn": "DB.EVAL.DATA", "stage_fqn": "DB.AGENTS.STAGE",
    }
    candidate.write_text(json.dumps({
        "schema_version": 2, "artifact_type": "candidate", "agent": "agent",
        "suite": "core", "eval_model": "agent_core", "run_name": "run",
        "timestamp": "20260827_000000", "summary": {}, "thresholds": {},
        "regression_tolerances": {}, "passed": False, "total_records": 1,
        "plan_schema_version": 2, "suite_signature": "suite", "plan_identity": identity,
        "agent_fqn": "DB.AGENTS.AGENT", "dataset_fqn": "DB.EVAL.DATA",
        "stage_fqn": "DB.AGENTS.STAGE", "metric_names": [],
        "ordered_ground_truth_refs": ["ref"], "status": "completed",
        "run_metadata": {
            "plan_identity": identity,
            "pre_start": {"default_version": "VERSION$1"},
            "post_completion": {"default_version": "VERSION$1"},
            "evaluated_version": "VERSION$1",
            "default_version_changed": False,
        },
    }))

    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "ok", "")

    result = verify_evaluations(
        _config(tmp_path), (VerifySelection(_plan(), tmp_path / "baseline.json"),),
        apply=True, allowed_targets=["sandbox"], allowed_databases=["DB"],
        poll_attempts=1, poll_interval=0, transient_retries=0,
        runner=CommandRunner(run), evaluate=lambda *_args, **_kwargs: candidate,
        render_plan=lambda *_args, **_kwargs: _plan(),
    )

    assert result["passed"] is False
    assert result["outcome"] == "quality_failed"
    assert result["suites"][0]["baseline_state"] == "not_established"