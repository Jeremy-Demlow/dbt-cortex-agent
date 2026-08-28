from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

# Evidence: TC-022-02 TC-022-06 TC-022-09
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.eval.lifecycle import PLAN_SCHEMA_VERSION, EvalPlan
from dbt_cortex_agent.eval.verify import (
    VerifySelection,
    build_verify_selections,
    verify_evaluations,
)


def _config(tmp_path):
    args = SimpleNamespace(
        project_dir=str(tmp_path),
        manifest=None,
        target="sandbox",
        connection="named",
        database="DB",
        schema=None,
        role="ROLE",
        warehouse="WH",
        artifact_dir=None,
        dbt_executable="dbt",
        snow_executable="snow",
    )
    return resolve_config(args, {})


def _plan(suite="core", **overrides):
    # A real EvalPlan, not a permissive stub: a SimpleNamespace silently accepts
    # any attribute, which previously masked a missing-field defect in the
    # plan-drift check.
    fields = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "agent_name": "agent",
        "suite_name": suite,
        "eval_model": f"agent_{suite}",
        "table_fqn": "DB.EVAL.DATA",
        "agent_fqn": "DB.AGENTS.AGENT",
        "stage_fqn": "DB.AGENTS.STAGE",
        "result_database": "DB",
        "result_schema": "EVAL",
        "target_name": "sandbox",
        "target_role": "ROLE",
        "target_database": "DB",
        "target_schema": "AGENTS",
        "target_warehouse": "WH",
        "native_eval_config": {},
        "dataset_name_token": "__RUN_NAME__",
        "config_filename_template": "__RUN_NAME__.yaml",
        "metric_names": [],
        "thresholds": {},
        "regression_tolerances": {},
        "ordered_ground_truth_refs": ["ref"],
        "suite_signature": f"signature-{suite}",
        "plan_identity": {"target_name": "sandbox"},
    }
    fields.update(overrides)
    return EvalPlan(**fields)


def test_verify_preview_is_deterministic_and_non_mutating(tmp_path):
    selections = (
        VerifySelection(_plan("safety"), tmp_path / "safety.json"),
        VerifySelection(_plan("core"), tmp_path / "core.json"),
    )

    result = verify_evaluations(
        _config(tmp_path),
        selections,
        apply=False,
        allowed_targets=[],
        allowed_databases=[],
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
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

    result = verify_evaluations(
        _config(tmp_path),
        (VerifySelection(_plan(), tmp_path / "baseline.json"),),
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
        runner=CommandRunner(run),
    )

    assert result["outcome"] == "infrastructure_failed"
    assert result["passed"] is None
    assert result["suites"][0]["execution"] == "failed"
    assert result["suites"][0]["error"] == "dbt failed"
    assert calls[0][:2] == ["dbt", "build"]


def test_plan_drift_is_detected_on_the_real_dataclass_field(tmp_path):
    # Pins the field the drift check reads. A prior revision compared a
    # nonexistent `plan_signature`, which raised AttributeError on every real
    # applied run while permissive test stubs hid the defect.
    assert not hasattr(_plan(), "plan_signature")
    assert _plan().suite_signature == "signature-core"

    drifted = _plan(suite_signature="signature-changed")
    result = verify_evaluations(
        _config(tmp_path),
        (VerifySelection(_plan(), tmp_path / "baseline.json"),),
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
        runner=CommandRunner(
            lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "ok", "")
        ),
        evaluate=lambda *_args, **_kwargs: tmp_path / "unused.json",
        render_plan=lambda *_args, **_kwargs: drifted,
    )

    assert result["outcome"] == "infrastructure_failed"
    assert "Evaluation plan changed" in result["error"]
    assert result["suites"][0]["execution"] == "failed"


def test_eval_verify_validates_all_plans_before_first_build(tmp_path):
    invalid = _plan("invalid", result_database="OTHER_DB")
    calls = []

    with pytest.raises(ValueError, match="OTHER_DB"):
        verify_evaluations(
            _config(tmp_path),
            (
                VerifySelection(_plan("core"), tmp_path / "core.json"),
                VerifySelection(invalid, tmp_path / "invalid.json"),
            ),
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            poll_attempts=1,
            poll_interval=0,
            transient_retries=0,
            runner=CommandRunner(
                lambda command, **kwargs: (
                    calls.append(command) or subprocess.CompletedProcess(command, 0, "", "")
                )
            ),
        )

    assert calls == []


def test_missing_baseline_uses_intrinsic_candidate_result(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate.json"
    identity = {
        "target_name": "sandbox",
        "agent_name": "agent",
        "suite_name": "core",
        "eval_model": "agent_core",
        "agent_fqn": "DB.AGENTS.AGENT",
        "dataset_fqn": "DB.EVAL.DATA",
        "stage_fqn": "DB.AGENTS.STAGE",
    }
    candidate.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "artifact_type": "candidate",
                "agent": "agent",
                "suite": "core",
                "eval_model": "agent_core",
                "run_name": "run",
                "timestamp": "20260827_000000",
                "summary": {},
                "thresholds": {},
                "regression_tolerances": {},
                "passed": False,
                "total_records": 1,
                "plan_schema_version": 2,
                "suite_signature": "suite",
                "plan_identity": identity,
                "agent_fqn": "DB.AGENTS.AGENT",
                "dataset_fqn": "DB.EVAL.DATA",
                "stage_fqn": "DB.AGENTS.STAGE",
                "metric_names": [],
                "ordered_ground_truth_refs": ["ref"],
                "status": "completed",
                "run_metadata": {
                    "plan_identity": identity,
                    "pre_start": {"default_version": "VERSION$1"},
                    "post_completion": {"default_version": "VERSION$1"},
                    "evaluated_version": "VERSION$1",
                    "default_version_changed": False,
                },
            }
        )
    )

    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "ok", "")

    result = verify_evaluations(
        _config(tmp_path),
        (VerifySelection(_plan(), tmp_path / "baseline.json"),),
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
        runner=CommandRunner(run),
        evaluate=lambda *_args, **_kwargs: candidate,
        render_plan=lambda *_args, **_kwargs: _plan(),
    )

    assert result["passed"] is False
    assert result["outcome"] == "quality_failed"
    assert result["suites"][0]["baseline_state"] == "not_established"


def test_later_suite_failure_preserves_completed_suite_result(tmp_path):
    candidate = tmp_path / "core-candidate.json"
    identity = {
        "target_name": "sandbox",
        "agent_name": "agent",
        "suite_name": "core",
        "eval_model": "agent_core",
        "agent_fqn": "DB.AGENTS.AGENT",
        "dataset_fqn": "DB.EVAL.DATA",
        "stage_fqn": "DB.AGENTS.STAGE",
    }
    candidate.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "artifact_type": "candidate",
                "agent": "agent",
                "suite": "core",
                "eval_model": "agent_core",
                "run_name": "run",
                "timestamp": "20260828_000000",
                "summary": {},
                "thresholds": {},
                "regression_tolerances": {},
                "passed": True,
                "total_records": 1,
                "plan_schema_version": 2,
                "suite_signature": "suite",
                "plan_identity": identity,
                "agent_fqn": "DB.AGENTS.AGENT",
                "dataset_fqn": "DB.EVAL.DATA",
                "stage_fqn": "DB.AGENTS.STAGE",
                "metric_names": [],
                "ordered_ground_truth_refs": ["ref"],
                "status": "completed",
                "run_metadata": {
                    "plan_identity": identity,
                    "pre_start": {"default_version": "VERSION$1"},
                    "post_completion": {"default_version": "VERSION$1"},
                    "evaluated_version": "VERSION$1",
                    "default_version_changed": False,
                },
            }
        )
    )
    plans = {
        "core": _plan("core"),
        "safety": _plan("safety"),
        "quality": _plan("quality"),
    }

    def evaluate(_config, plan, **_kwargs):
        if plan.suite_name == "safety":
            raise RuntimeError("evaluation service unavailable")
        return candidate

    result = verify_evaluations(
        _config(tmp_path),
        (
            VerifySelection(plans["core"], tmp_path / "core-baseline.json"),
            VerifySelection(plans["safety"], tmp_path / "safety-baseline.json"),
            VerifySelection(plans["quality"], tmp_path / "quality-baseline.json"),
        ),
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
        runner=CommandRunner(
            lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "ok", "")
        ),
        evaluate=evaluate,
        render_plan=lambda _config, *, suite_name, **_kwargs: plans[suite_name],
    )

    assert result["outcome"] == "infrastructure_failed"
    assert result["passed"] is None
    assert result["quality_passed"] is True
    assert result["suites"][0]["execution"] == "completed"
    assert result["suites"][0]["candidate"] == str(candidate)
    assert result["suites"][1]["execution"] == "failed"
    assert result["suites"][1]["error"] == "evaluation service unavailable"
    assert result["suites"][2]["execution"] == "not_run"
    assert result["suites"][2]["error"] is None


def test_unexpected_programming_error_is_not_mislabeled_as_infrastructure(tmp_path):
    with pytest.raises(AssertionError, match="programming defect"):
        verify_evaluations(
            _config(tmp_path),
            (VerifySelection(_plan(), tmp_path / "baseline.json"),),
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            poll_attempts=1,
            poll_interval=0,
            transient_retries=0,
            runner=CommandRunner(
                lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "ok", "")
            ),
            evaluate=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("programming defect")
            ),
            render_plan=lambda *_args, **_kwargs: _plan(),
        )
