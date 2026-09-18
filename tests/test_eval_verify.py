from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

# Evidence: TC-022-02 TC-022-06 TC-022-09 TC-031-04
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.eval.baseline import build_baseline
from dbt_cortex_agent.eval.lifecycle import PLAN_SCHEMA_VERSION, EvalPlan
from dbt_cortex_agent.eval.results import build_candidate
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
        "metric_names": ["answer_correctness"],
        "thresholds": {},
        "regression_tolerances": {},
        "ordered_ground_truth_refs": ["ref"],
        "suite_signature": f"signature-{suite}",
        "plan_identity": {
            "target_name": "sandbox",
            "agent_name": "agent",
            "suite_name": suite,
            "eval_model": f"agent_{suite}",
            "agent_fqn": "DB.AGENTS.AGENT",
            "dataset_fqn": "DB.EVAL.DATA",
            "stage_fqn": "DB.AGENTS.STAGE",
        },
    }
    fields.update(overrides)
    return EvalPlan(**fields)


def _candidate(plan=None):
    plan = plan or _plan()
    return build_candidate(
        plan=plan,
        run_name="run",
        rows=[
            {"ground_truth_ref": "ref", "metric_name": metric, "eval_agg_score": 1.0}
            for metric in plan.metric_names
        ],
        provenance={
            "plan_identity": plan.plan_identity,
            "pre_start": {"default_version": "VERSION$1"},
            "post_completion": {"default_version": "VERSION$1"},
            "evaluated_version": "VERSION$1",
            "default_version_changed": False,
        },
    )


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
    candidate.write_text(json.dumps({**_candidate(), "passed": False}))

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


@pytest.mark.parametrize("connector_error", [False, True])
def test_later_suite_failure_preserves_completed_suite_result(tmp_path, connector_error):
    candidate = tmp_path / "core-candidate.json"
    candidate.write_text(json.dumps(_candidate()))
    plans = {
        "core": _plan("core"),
        "safety": _plan("safety"),
        "quality": _plan("quality"),
    }

    def evaluate(_config, plan, **_kwargs):
        if plan.suite_name == "safety":
            error = (
                type("OperationalError", (Exception,), {"__module__": "snowflake.connector.errors"})
                if connector_error
                else RuntimeError
            )
            raise error("evaluation service unavailable")
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


@pytest.mark.parametrize("error_type", [AssertionError, TypeError, AttributeError])
def test_unexpected_programming_error_is_not_mislabeled_as_infrastructure(tmp_path, error_type):
    with pytest.raises(error_type, match="programming defect"):
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
                error_type("programming defect")
            ),
            render_plan=lambda *_args, **_kwargs: _plan(),
        )


@pytest.mark.parametrize("established", [False, True])
@pytest.mark.parametrize(
    "damage",
    [
        "none",
        "drift",
        "failed",
        "running",
        "passed_null",
        "passed_string",
        "null",
        "duplicate",
        "nan",
        "inf",
    ],
)
def test_verify_real_candidate_gate_never_greens_invalid_evidence(tmp_path, established, damage):
    baseline = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    candidate = _candidate()
    if established:
        baseline.write_text(json.dumps(build_baseline(candidate)))
    if damage == "drift":
        candidate["run_metadata"]["post_completion"]["default_version"] = "VERSION$2"
        candidate["run_metadata"]["default_version_changed"] = True
        candidate.update(status="indeterminate", passed=False)
    elif damage == "failed":
        candidate["passed"] = False
    elif damage == "running":
        candidate["status"] = "running"
    elif damage.startswith("passed_"):
        candidate["passed"] = None if damage == "passed_null" else "true"
    elif damage == "duplicate":
        candidate["results"].append({**candidate["results"][0], "record_id": "other"})
    elif damage in {"null", "nan", "inf"}:
        candidate["results"][0]["eval_agg_score"] = {
            "null": None,
            "nan": float("nan"),
            "inf": float("inf"),
        }[damage]
    candidate_path.write_text(json.dumps(candidate))
    result = verify_evaluations(
        _config(tmp_path),
        (VerifySelection(_plan(), baseline),),
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
        runner=CommandRunner(
            lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "ok", "")
        ),
        evaluate=lambda *_args, **_kwargs: candidate_path,
        render_plan=lambda *_args, **_kwargs: _plan(),
    )
    if damage == "none":
        assert result["passed"] is True
        assert result["outcome"] == "passed"
    elif damage in {"null", "duplicate", "nan", "inf"}:
        assert result["passed"] is None
        assert result["outcome"] == "infrastructure_failed"
    else:
        assert result["passed"] is False
        assert result["outcome"] == "quality_failed"
    assert result["suites"][0]["baseline_state"] == (
        "established" if established else "not_established"
    )


@pytest.mark.parametrize("policy", ["thresholds", "regression_tolerances"])
def test_verify_rejects_unknown_policy_in_later_suite_before_effects(tmp_path, policy):
    with pytest.raises(ValueError, match="undeclared metrics: typo_metric"):
        verify_evaluations(
            _config(tmp_path),
            (
                VerifySelection(_plan(), tmp_path / "core.json"),
                VerifySelection(
                    _plan("later", **{policy: {"typo_metric": 0.1}}), tmp_path / "later.json"
                ),
            ),
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            poll_attempts=1,
            poll_interval=0,
            transient_retries=0,
            runner=CommandRunner(lambda *_args, **_kwargs: pytest.fail("dbt build executed")),
            evaluate=lambda *_args, **_kwargs: pytest.fail("paid evaluation executed"),
        )


@pytest.mark.parametrize("established", [False, True])
@pytest.mark.parametrize("score", [None, float("nan"), float("inf"), "absent"])
@pytest.mark.parametrize("tool_metric", ["tool_selection_accuracy", "tool_execution_accuracy"])
def test_verify_honors_excluded_tool_observations(tmp_path, established, score, tool_metric):
    plan = _plan(metric_names=["answer_correctness", tool_metric])
    candidate = _candidate(plan)
    for row in candidate["results"]:
        row["test_type"] = "out_of_scope"
    if score == "absent":
        candidate["results"].pop()
    else:
        candidate["results"][-1]["eval_agg_score"] = score
    candidate["summary"].pop(tool_metric)
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate))
    baseline_path = tmp_path / "baseline.json"
    if established:
        baseline_path.write_text(json.dumps(build_baseline(candidate)))
    result = verify_evaluations(
        _config(tmp_path),
        (VerifySelection(plan, baseline_path),),
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
        runner=CommandRunner(
            lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "ok", "")
        ),
        evaluate=lambda *_args, **_kwargs: candidate_path,
        render_plan=lambda *_args, **_kwargs: plan,
    )
    assert result["passed"] is True


def _verify_one(tmp_path, candidate_path, baseline, plan=None):
    plan = plan or _plan()
    return verify_evaluations(
        _config(tmp_path),
        (VerifySelection(plan, baseline),),
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
        runner=CommandRunner(
            lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "ok", "")
        ),
        evaluate=lambda *_args, **_kwargs: candidate_path,
        render_plan=lambda *_args, **_kwargs: plan,
    )


@pytest.mark.parametrize("failure", ["baseline", "gate", "candidate"])
def test_post_candidate_failure_retains_execution_evidence(tmp_path, monkeypatch, failure):
    candidate_path = tmp_path / "candidate.json"
    baseline = tmp_path / "baseline.json"
    candidate_path.write_text(json.dumps(_candidate()))
    baseline.write_text(json.dumps(build_baseline(_candidate())))
    if failure == "baseline":
        baseline.write_text("not json")
    elif failure == "candidate":
        candidate_path.write_text("not json")
    else:
        monkeypatch.setattr(
            "dbt_cortex_agent.eval.verify.compare_results",
            lambda *_args: (_ for _ in ()).throw(OSError("gate unavailable")),
        )
    result = _verify_one(tmp_path, candidate_path, baseline)
    assert result["outcome"] == "infrastructure_failed"
    assert result["passed"] is None
    suite = result["suites"][0]
    assert suite["candidate"] == str(candidate_path)
    assert suite["execution"] == "completed"
    assert suite["gate"] == "error"
    assert suite["passed"] is None


@pytest.mark.parametrize("established", [False, True])
@pytest.mark.parametrize(
    "field", ["identity", "suite_signature", "thresholds", "regression_tolerances"]
)
def test_verify_binds_current_plan_even_for_self_consistent_candidate(tmp_path, established, field):
    candidate = _candidate()
    if field == "identity":
        candidate["plan_identity"]["target_name"] = "unrelated"
    elif field == "suite_signature":
        candidate[field] = "unrelated"
    else:
        candidate[field] = {"answer_correctness": 0.1}
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate))
    baseline = tmp_path / "baseline.json"
    if established:
        baseline.write_text(json.dumps(build_baseline(candidate)))
    result = _verify_one(tmp_path, candidate_path, baseline)
    assert result["outcome"] == "infrastructure_failed"
    assert "does not match current plan" in result["error"]
    assert result["suites"][0]["candidate"] == str(candidate_path)


def test_verify_gates_exact_loaded_candidate_without_reopening(tmp_path, monkeypatch):
    from dbt_cortex_agent.eval.results import load_result

    candidate_path = tmp_path / "candidate.json"
    baseline = tmp_path / "baseline.json"
    candidate_path.write_text(json.dumps(_candidate()))
    baseline.write_text(json.dumps(build_baseline(_candidate())))
    loads = []

    def load(path, expected_type):
        loads.append((path, expected_type))
        value = load_result(path, expected_type)
        if expected_type == "candidate":
            candidate_path.write_text("replaced after load")
        return value

    monkeypatch.setattr("dbt_cortex_agent.eval.verify.load_result", load)
    assert _verify_one(tmp_path, candidate_path, baseline)["passed"] is True
    assert loads == [(candidate_path, "candidate"), (baseline, "baseline")]


@pytest.mark.parametrize(
    "field, value",
    [
        ("agent_name", "different_agent"),
        ("suite_name", "different_suite"),
        ("eval_model", "different_model"),
        ("agent_fqn", "DB.AGENTS.OTHER"),
        ("table_fqn", "DB.EVAL.OTHER"),
        ("stage_fqn", "DB.AGENTS.OTHER"),
        ("metric_names", ["tool_selection_accuracy"]),
        ("ordered_ground_truth_refs", ["other"]),
    ],
)
def test_verify_rejects_consistent_foreign_candidate_fields(tmp_path, field, value):
    candidate = _candidate()
    identity_keys = {
        "agent_name": ("agent", "agent_name"),
        "suite_name": ("suite", "suite_name"),
        "eval_model": ("eval_model", "eval_model"),
        "agent_fqn": ("agent_fqn", "agent_fqn"),
        "table_fqn": ("dataset_fqn", "dataset_fqn"),
        "stage_fqn": ("stage_fqn", "stage_fqn"),
    }
    if field in identity_keys:
        artifact_field, identity_field = identity_keys[field]
        candidate[artifact_field] = value
        candidate["plan_identity"][identity_field] = value
    elif field == "metric_names":
        candidate[field] = value
        candidate["results"][0]["metric_name"] = value[0]
        candidate["summary"][value[0]] = candidate["summary"].pop("answer_correctness")
    else:
        candidate[field] = value
        candidate["results"][0]["ground_truth_ref"] = value[0]
    candidate_path = tmp_path / "candidate.json"
    baseline = tmp_path / "baseline.json"
    candidate_path.write_text(json.dumps(candidate))
    baseline.write_text(json.dumps(build_baseline(candidate)))
    result = _verify_one(tmp_path, candidate_path, baseline)
    assert "does not match current plan" in result["error"]
    assert result["suites"][0]["gate"] == "error"


def test_current_plan_identity_drift_blocks_paid_run_even_with_same_signature(tmp_path):
    original = _plan()
    drifted = _plan(plan_identity={**original.plan_identity, "target_name": "other"})
    result = verify_evaluations(
        _config(tmp_path),
        (VerifySelection(original, tmp_path / "baseline.json"),),
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
        runner=CommandRunner(
            lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "ok", "")
        ),
        evaluate=lambda *_args, **_kwargs: pytest.fail("paid evaluation executed"),
        render_plan=lambda *_args, **_kwargs: drifted,
    )
    assert "Evaluation plan changed" in result["error"]
    assert result["suites"][0]["execution"] == "failed"


def test_later_baseline_error_retains_both_candidate_paths_and_prior_gate(tmp_path):
    plans = {suite: _plan(suite) for suite in ("core", "later", "unused")}
    paths = {suite: tmp_path / f"{suite}.json" for suite in plans}
    for suite, plan in plans.items():
        paths[suite].write_text(json.dumps(_candidate(plan)))
    bad_baseline = tmp_path / "bad-baseline.json"
    bad_baseline.write_text("invalid")
    result = verify_evaluations(
        _config(tmp_path),
        tuple(
            VerifySelection(plan, bad_baseline if suite == "later" else tmp_path / "absent")
            for suite, plan in plans.items()
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
        evaluate=lambda _config, plan, **_kwargs: paths[plan.suite_name],
        render_plan=lambda _config, *, suite_name, **_kwargs: plans[suite_name],
    )
    assert [item["candidate"] for item in result["suites"]] == [
        str(paths["core"]),
        str(paths["later"]),
        None,
    ]
    assert [item["gate"] for item in result["suites"]] == ["passed", "error", "not_run"]
    assert [item["execution"] for item in result["suites"]] == ["completed", "completed", "not_run"]


@pytest.mark.parametrize("phase", ["cursor", "execute"])
@pytest.mark.parametrize("error_type", [OSError, AssertionError, TypeError, AttributeError])
def test_evaluation_acquisition_cleanup_preserves_primary(tmp_path, phase, error_type):
    from dbt_cortex_agent.eval.lifecycle import run_evaluation

    closed = []
    primary = error_type("primary")

    class Cursor:
        def execute(self, *_args):
            if phase == "execute":
                raise primary

        def close(self):
            closed.append("cursor")
            raise OSError("cursor close")

    class Connection:
        def cursor(self):
            if phase == "cursor":
                raise primary
            return Cursor()

        def close(self):
            closed.append("connection")
            raise OSError("connection close")

    with pytest.raises(error_type) as failure:
        run_evaluation(
            _config(tmp_path),
            _plan(),
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            poll_attempts=1,
            poll_interval=0,
            transient_retries=0,
            connect=lambda _name: Connection(),
        )
    assert failure.value is primary
    assert closed == (["connection"] if phase == "cursor" else ["cursor", "connection"])
    assert failure.value.cleanup_errors
