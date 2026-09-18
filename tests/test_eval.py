from __future__ import annotations

import builtins
import hashlib
import importlib
import json
import subprocess
from argparse import Namespace
from dataclasses import replace

import pytest

# Evidence: TC-022-07 TC-022-08 TC-022-10 TC-023-10 TC-023-11 TC-025-09
from dbt_cortex_agent.artifacts import ARTIFACT_SCHEMA_VERSION
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.eval.baseline import (
    accept_baseline,
    build_baseline,
)
from dbt_cortex_agent.eval.compare import compare_results
from dbt_cortex_agent.eval.dataset import (
    annotate_rows,
    validate_eval_meta,
    validate_snapshot,
    validate_table,
)
from dbt_cortex_agent.eval.gate import gate_candidate
from dbt_cortex_agent.eval.lifecycle import (
    TERMINAL_SUCCESS,
    _default_connect,
    _fetch_rows,
    build_plan,
    flatten_status_details,
    is_retryable,
    poll,
    run_evaluation,
)
from dbt_cortex_agent.eval.results import (
    build_candidate,
    compute_summary,
    load_result,
    write_candidate,
)


def test_eval_package_does_not_advertise_lifecycle_api():
    package = importlib.import_module("dbt_cortex_agent.eval")

    assert not hasattr(package, "EvalPlan")
    assert not hasattr(package, "build_plan")
    assert not hasattr(package, "run_evaluation")


def test_missing_eval_dependency_message_names_runtime_extra(monkeypatch):
    real_import = builtins.__import__

    def fail_snowflake(name, *args, **kwargs):
        if name == "snowflake.connector":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_snowflake)
    with pytest.raises(RuntimeError, match=r"dbt-cortex-agent\[runtime\]"):
        _default_connect("conn")


def _manifest(*, duplicate=False, agent_object=True):
    eval_meta = {
        "enabled": True,
        "name": "core",
        "agent": "orders_assistant",
        "stage": "DB.EVAL.EVAL_STAGE",
        "metrics": [
            "answer_correctness",
            "tool_selection_accuracy",
            "tool_execution_accuracy",
        ],
        "thresholds": {"answer_correctness": 0.6, "tool_selection_accuracy": 0.8},
        "regression_tolerances": {"tool_selection_accuracy": 0.05},
        "description": "Core suite",
    }
    if agent_object:
        eval_meta["agent_object"] = "ORDERS_ASSISTANT_EVAL"
    nodes = {
        "model.consumer.eval_orders": {
            "unique_id": "model.consumer.eval_orders",
            "name": "eval_orders",
            "database": "DB",
            "schema": "EVAL",
            "alias": "EVAL_ORDERS",
            "config": {"meta": {"cortex_eval": eval_meta}},
        }
    }
    if duplicate:
        nodes["model.consumer.eval_orders_copy"] = {
            **nodes["model.consumer.eval_orders"],
            "unique_id": "model.consumer.eval_orders_copy",
            "name": "eval_orders_copy",
        }
    return {
        "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
        "exposures": {
            "exposure.consumer.orders": {
                "name": "orders_assistant",
                "config": {
                    "meta": {
                        "cortex_agent": {
                            "enabled": True,
                            "snowflake_name": "ORDERS_ASSISTANT",
                            "naming": {"sandbox_eval": "ORDERS_ASSISTANT_SANDBOX_EVAL"},
                        }
                    }
                },
            }
        },
        "nodes": nodes,
    }


def _config(tmp_path, manifest):
    target = tmp_path / "target"
    target.mkdir(parents=True)
    (target / "manifest.json").write_text(json.dumps(manifest))
    return resolve_config(
        Namespace(
            project_dir=str(tmp_path),
            manifest=None,
            target="sandbox",
            connection="conn",
            database="DB",
            schema="AGENT_SCHEMA",
            role="ROLE",
            warehouse="WH",
            artifact_dir="artifacts",
            dbt_executable=None,
            snow_executable=None,
        ),
        env={},
    )


def _plan_payload(*, refs=None, tolerances=None, result_database="DB"):
    token = "__DBT_CORTEX_AGENT_DATASET_NAME__"
    identity = {
        "agent_name": "orders_assistant",
        "suite_name": "core",
        "eval_model": "eval_orders",
        "agent_fqn": "DB.AGENT_SCHEMA.ORDERS_ASSISTANT",
        "dataset_fqn": "DB.EVAL.EVAL_ORDERS",
        "stage_fqn": "DB.AGENT_SCHEMA.EVAL_CONFIG_STAGE",
        "target_name": "sandbox",
        "target_role": "EVAL_ROLE",
        "target_database": "DB",
        "target_schema": "AGENT_SCHEMA",
        "target_warehouse": "WH",
        "result_database": result_database,
        "result_schema": "EVAL_RESULTS",
    }
    native = {
        "dataset": {
            "dataset_type": "CORTEX AGENT",
            "table_name": identity["dataset_fqn"],
            "dataset_name": token,
            "column_mapping": {"query_text": "INPUT_QUERY", "ground_truth": "OUTPUT"},
        },
        "evaluation": {
            "agent_params": {"agent_name": identity["agent_fqn"], "agent_type": "CORTEX AGENT"},
            "run_params": {"label": "orders_assistant/core", "description": "Core suite"},
            "source_metadata": {"type": "dataset", "dataset_name": token},
        },
        "metrics": ["answer_correctness", "tool_selection_accuracy"],
    }
    payload = {
        "schema_version": 2,
        "identity": identity,
        "native_eval_config": native,
        "dataset_name_token": token,
        "config_filename_template": "eval_orders__RUN_NAME__.json",
        "metric_names": ["answer_correctness", "tool_selection_accuracy"],
        "thresholds": {"answer_correctness": 0.6, "tool_selection_accuracy": 0.8},
        "regression_tolerances": tolerances or {"tool_selection_accuracy": 0.05},
        "ordered_ground_truth_refs": refs or ["q1", "q2"],
    }
    signed = {
        "plan_schema_version": payload["schema_version"],
        "identity": identity,
        "native_eval_config": native,
        "metric_names": payload["metric_names"],
        "thresholds": payload["thresholds"],
        "regression_tolerances": payload["regression_tolerances"],
        "ordered_ground_truth_refs": payload["ordered_ground_truth_refs"],
    }
    payload["signature_material"] = json.dumps(signed, separators=(",", ":"))
    payload["suite_signature"] = hashlib.md5(payload["signature_material"].encode()).hexdigest()
    return payload


def test_build_plan_consumes_dbt_payload_without_reconstructing_identity(tmp_path):
    plan = build_plan(
        _config(tmp_path, _manifest()),
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(),
    )
    assert plan.agent_fqn == "DB.AGENT_SCHEMA.ORDERS_ASSISTANT"
    assert not hasattr(plan, "projection")
    assert plan.table_fqn == "DB.EVAL.EVAL_ORDERS"
    assert plan.stage_fqn == "DB.AGENT_SCHEMA.EVAL_CONFIG_STAGE"
    assert plan.target_role == "EVAL_ROLE"
    assert plan.thresholds == {"answer_correctness": 0.6, "tool_selection_accuracy": 0.8}


def test_build_plan_runs_fresh_parse_then_package_qualified_plan_macro(tmp_path):
    payload = _plan_payload()

    class FakeRunner:
        def __init__(self):
            self.calls = []

        def run(self, command, *, cwd=None):
            self.calls.append(list(command))
            stdout = (
                f"CORTEX_EVAL_PLAN_JSON={json.dumps(payload, separators=(',', ':'))}\n"
                if "run-operation" in command
                else ""
            )
            return subprocess.CompletedProcess(command, 0, stdout, "")

    fake = FakeRunner()
    build_plan(
        _config(tmp_path, _manifest()),
        agent_name="orders_assistant",
        suite_name="core",
        runner=fake,
    )
    assert fake.calls[0][1] == "parse"
    assert fake.calls[1][1:3] == [
        "run-operation",
        "dbt_cortex_agent.cortex_eval__execution_plan",
    ]


def test_build_plan_passes_resolved_environment_to_parse_and_macro(tmp_path):
    payload = _plan_payload()

    class FakeRunner:
        def __init__(self):
            self.envs = []

        def run(self, command, *, cwd=None, env=None):
            self.envs.append(env)
            stdout = (
                f"CORTEX_EVAL_PLAN_JSON={json.dumps(payload, separators=(',', ':'))}\n"
                if "run-operation" in command
                else ""
            )
            return subprocess.CompletedProcess(command, 0, stdout, "")

    config = _config(tmp_path, _manifest())
    context = type("Context", (), {"dbt_env": {"SNOWFLAKE_ACCOUNT": "acct"}})()
    config = __import__("dataclasses").replace(config, execution_context=context)
    fake = FakeRunner()

    build_plan(config, agent_name="orders_assistant", suite_name="core", runner=fake)

    assert fake.envs == [
        {"SNOWFLAKE_ACCOUNT": "acct"},
        {"SNOWFLAKE_ACCOUNT": "acct"},
    ]


def test_build_plan_fails_closed_for_tampered_or_duplicate_refs(tmp_path):
    payload = _plan_payload()
    payload["identity"]["agent_fqn"] = "DB.AGENT_SCHEMA.WRONG"
    with pytest.raises(ValueError, match="signed fields"):
        build_plan(
            _config(tmp_path, _manifest()),
            agent_name="orders_assistant",
            suite_name="core",
            plan_payload=payload,
        )
    with pytest.raises(ValueError, match="non-empty and unique"):
        build_plan(
            _config(tmp_path / "duplicate", _manifest()),
            agent_name="orders_assistant",
            suite_name="core",
            plan_payload=_plan_payload(refs=["q1", "q1"]),
        )


def test_build_plan_requires_authoritative_target_role(tmp_path):
    payload = _plan_payload()
    payload["identity"]["target_role"] = None
    signed = json.loads(payload["signature_material"])
    signed["identity"]["target_role"] = None
    payload["signature_material"] = json.dumps(signed, separators=(",", ":"))
    payload["suite_signature"] = hashlib.md5(payload["signature_material"].encode()).hexdigest()

    with pytest.raises(ValueError, match="target_role is required"):
        build_plan(
            _config(tmp_path, _manifest()),
            agent_name="orders_assistant",
            suite_name="core",
            plan_payload=payload,
        )


def test_build_plan_rejects_projection_and_native_config_agent_mismatch(tmp_path):
    projection = _plan_payload()
    projection["identity"]["projection"] = "native_eval"
    signed = json.loads(projection["signature_material"])
    signed["identity"]["projection"] = "native_eval"
    projection["signature_material"] = json.dumps(signed, separators=(",", ":"))
    projection["suite_signature"] = hashlib.md5(
        projection["signature_material"].encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="must not contain projection"):
        build_plan(
            _config(tmp_path, _manifest()),
            agent_name="orders_assistant",
            suite_name="core",
            plan_payload=projection,
        )

    mismatch = _plan_payload()
    mismatch["native_eval_config"]["evaluation"]["agent_params"]["agent_name"] = "DB.S.WRONG"
    signed = json.loads(mismatch["signature_material"])
    signed["native_eval_config"] = mismatch["native_eval_config"]
    mismatch["signature_material"] = json.dumps(signed, separators=(",", ":"))
    mismatch["suite_signature"] = hashlib.md5(mismatch["signature_material"].encode()).hexdigest()
    with pytest.raises(ValueError, match="native config Agent must match"):
        build_plan(
            _config(tmp_path / "mismatch", _manifest()),
            agent_name="orders_assistant",
            suite_name="core",
            plan_payload=mismatch,
        )


def test_metric_validation_fails_before_execution():
    with pytest.raises(ValueError, match="undeclared metrics"):
        validate_eval_meta({"metrics": ["answer_correctness"], "thresholds": {"missing": 0.5}})
    with pytest.raises(ValueError, match="requires a prompt"):
        validate_eval_meta({"metrics": [{"name": "quality"}]})
    with pytest.raises(ValueError, match="must define all three"):
        validate_eval_meta(
            {
                "metrics": [
                    {"name": "quality", "prompt": "score", "score_ranges": {"min_score": [1, 3]}}
                ]
            }
        )


class PollCursor:
    def __init__(self, statuses):
        self.statuses = iter(statuses)
        self.current = None
        self.description = [("RUN_NAME",), ("AGENT",), ("OTHER",), ("STATUS",), ("STATUS_DETAILS",)]
        self.calls = 0

    def execute(self, sql, params=None):
        self.calls += 1
        self.current = next(self.statuses)

    def fetchall(self):
        status, details = self.current
        return [("run", "agent", None, status, details)]


def test_poll_uses_exact_terminal_states_and_bounded_attempts():
    cursor = PollCursor(
        [("INVOCATION_COMPLETED", ""), ("COMPUTATION_IN_PROGRESS", ""), ("COMPLETED", "")]
    )
    sleeps = []
    result = poll(cursor, "run", "@stage/config", attempts=5, interval=2, sleep=sleeps.append)
    assert result.status in TERMINAL_SUCCESS
    assert cursor.calls == 3
    assert sleeps == [2, 2]

    timeout = poll(
        PollCursor([("CREATED", ""), ("INVOCATION_IN_PROGRESS", "")]),
        "run",
        "@stage/config",
        attempts=2,
        interval=0,
        sleep=lambda _: None,
    )
    assert timeout.status == "TIMEOUT"
    assert timeout.observed_status == "INVOCATION_IN_PROGRESS"


def test_poll_preserves_partial_status_when_attempts_exhausted():
    timeout = poll(
        PollCursor(
            [
                ("INVOCATION_IN_PROGRESS", ""),
                ("INVOCATION_PARTIALLY_COMPLETED", ""),
            ]
        ),
        "run",
        "@stage/config",
        attempts=2,
        interval=0,
        sleep=lambda _: None,
    )

    assert timeout.status == "TIMEOUT"
    assert timeout.observed_status == "INVOCATION_PARTIALLY_COMPLETED"
    assert timeout.details == "poll attempts exhausted"


def test_status_detail_classification_handles_json_and_is_bounded():
    assert (
        flatten_status_details('["Invocation failed", "rate limit"]')
        == "Invocation failed; rate limit"
    )
    assert is_retryable('["Invocation failed"]') is True
    assert is_retryable("Metric logical_consistency failed") is False


def test_poll_whitelists_native_diagnostic_identifiers():
    class DiagnosticCursor:
        description = [
            ("STATUS",),
            ("STATUS_DETAILS",),
            ("REQUEST_ID",),
            ("INFERENCE_ID",),
            ("ERROR_CODE",),
            ("INPUT",),
        ]

        def execute(self, sql, params=None):
            return None

        def fetchall(self):
            return [
                ("FAILED", "private failure text", "request-1", "inference-1", 399502, "secret")
            ]

    result = poll(
        DiagnosticCursor(), "run", "@stage/config", attempts=1, interval=0, sleep=lambda _: None
    )

    assert result.request_ids == ("request-1",)
    assert result.inference_ids == ("inference-1",)
    assert result.error_code == "399502"


def test_result_fetch_retries_empty_and_unscored_rows_to_bound():
    class Cursor:
        description = [("METRIC_NAME",)]

        def __init__(self):
            self.calls = 0

        def execute(self, sql, params=None):
            self.calls += 1

        def fetchall(self):
            return (
                []
                if self.calls == 1
                else [(None,)]
                if self.calls == 2
                else [("answer_correctness",)]
            )

    plan = type(
        "Plan",
        (),
        {
            "agent_fqn": "DB.S.AGENT",
            "ordered_ground_truth_refs": ["q1"],
            "metric_names": ["answer_correctness"],
        },
    )()
    cursor = Cursor()
    sleeps = []

    assert _fetch_rows(cursor, plan, "run", retries=2, sleep=sleeps.append, snapshot=()) == [
        {"metric_name": "answer_correctness"}
    ]
    assert cursor.calls == 3
    assert sleeps == [1, 1]


def test_result_fetch_retries_partial_scored_rows_until_complete():
    class Cursor:
        description = [
            ("INPUT",),
            ("METRIC_NAME",),
            ("EVAL_AGG_SCORE",),
        ]

        def __init__(self):
            self.calls = 0

        def execute(self, sql, params=None):
            assert "GET_AI_EVALUATION_DATA" in sql
            self.calls += 1

        def fetchall(self):
            rows = [("Revenue?", "answer_correctness", 0.8)]
            if self.calls > 1:
                rows.append(("Orders?", "answer_correctness", 0.9))
            return rows

    plan = type(
        "Plan",
        (),
        {
            "agent_fqn": "DB.S.AGENT",
            "table_fqn": "DB.S.DATA",
            "ordered_ground_truth_refs": ["q1", "q2"],
            "metric_names": ["answer_correctness"],
        },
    )()
    cursor = Cursor()
    sleeps = []

    rows = _fetch_rows(
        cursor,
        plan,
        "run",
        retries=2,
        sleep=sleeps.append,
        snapshot=(("Revenue?", "in_scope", "q1"), ("Orders?", "in_scope", "q2")),
    )

    assert len(rows) == 2
    assert cursor.calls == 2
    assert sleeps == [1]


def _rows():
    return [
        {
            "record_id": "r1",
            "input_id": "i1",
            "ground_truth_ref": "q1",
            "metric_name": "answer_correctness",
            "eval_agg_score": 0.8,
            "test_type": "in_scope",
        },
        {
            "record_id": "r2",
            "input_id": "i2",
            "ground_truth_ref": "q2",
            "metric_name": "answer_correctness",
            "eval_agg_score": 0.4,
            "test_type": "out_of_scope",
        },
        {
            "record_id": "r1",
            "input_id": "i1",
            "ground_truth_ref": "q1",
            "metric_name": "tool_selection_accuracy",
            "eval_agg_score": 1.0,
            "test_type": "in_scope",
        },
        {
            "record_id": "r2",
            "input_id": "i2",
            "ground_truth_ref": "q2",
            "metric_name": "tool_selection_accuracy",
            "eval_agg_score": 0.0,
            "test_type": "out_of_scope",
        },
    ]


def test_candidate_is_boundary_aware_and_provenance_rich(tmp_path):
    plan = build_plan(
        _config(tmp_path, _manifest()),
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(),
    )
    candidate = build_candidate(
        plan=plan,
        run_name="run-1",
        rows=_rows(),
        provenance={
            "agent_fqn": plan.agent_fqn,
            "plan_identity": plan.plan_identity,
            "evaluated_version": "VERSION$7",
            "pre_start": {"default_version": "VERSION$7", "aliases": {}},
            "post_completion": {"default_version": "VERSION$7", "aliases": {}},
            "default_version_changed": False,
        },
    )

    assert candidate["summary"]["answer_correctness"] == {"avg": pytest.approx(0.6), "n": 2}
    assert candidate["summary"]["tool_selection_accuracy"] == {"avg": 1.0, "n": 1}
    assert candidate["ordered_ground_truth_refs"] == ["q1", "q2"]
    assert candidate["run_metadata"]["evaluated_version"] == "VERSION$7"
    assert candidate["regression_tolerances"] == {"tool_selection_accuracy": 0.05}


@pytest.mark.parametrize("score", [float("nan"), float("inf"), "-Infinity"])
def test_candidate_summary_rejects_non_finite_scores(score):
    rows = _rows()
    rows[0]["eval_agg_score"] = score

    with pytest.raises(ValueError, match="finite number"):
        compute_summary(rows)


def test_candidate_write_refuses_collision(tmp_path):
    plan = build_plan(
        _config(tmp_path, _manifest()),
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(),
    )
    candidate = build_candidate(
        plan=plan,
        run_name="same_run",
        rows=_rows(),
        provenance={
            "agent_fqn": plan.agent_fqn,
            "plan_identity": plan.plan_identity,
            "evaluated_version": "VERSION$7",
            "pre_start": {"default_version": "VERSION$7", "aliases": {}},
            "post_completion": {"default_version": "VERSION$7", "aliases": {}},
            "default_version_changed": False,
        },
    )

    write_candidate(candidate, tmp_path / "artifacts")
    with pytest.raises(FileExistsError, match="already exists"):
        write_candidate(candidate, tmp_path / "artifacts")


def _result(*, score=0.8, passed=True, ids=None):
    plan_identity = {
        "agent_name": "orders_assistant",
        "suite_name": "core",
        "eval_model": "eval_orders",
        "agent_fqn": "DB.S.AGENT",
        "dataset_fqn": "DB.EVAL.TABLE",
        "stage_fqn": "DB.S.STAGE",
    }
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "candidate",
        "agent": "orders_assistant",
        "suite": "core",
        "eval_model": "eval_orders",
        "run_name": "run",
        "timestamp": "20260804_000000",
        "run_metadata": {
            "agent_fqn": "DB.S.AGENT",
            "plan_identity": plan_identity,
            "evaluated_version": "VERSION$1",
            "git_sha": "abc",
            "pre_start": {"default_version": "VERSION$1", "aliases": {}},
            "post_completion": {"default_version": "VERSION$1", "aliases": {}},
            "default_version_changed": False,
        },
        "plan_schema_version": 2,
        "suite_signature": "abc123",
        "plan_identity": plan_identity,
        "agent_fqn": "DB.S.AGENT",
        "dataset_fqn": "DB.EVAL.TABLE",
        "stage_fqn": "DB.S.STAGE",
        "metric_names": ["answer_correctness"],
        "status": "completed",
        "summary": {"answer_correctness": {"avg": score, "n": 2}},
        "thresholds": {"answer_correctness": 0.6},
        "regression_tolerances": {"answer_correctness": 0.05},
        "passed": passed,
        "total_records": 2,
        "ordered_ground_truth_refs": ids or ["q1", "q2"],
        "results": [
            {"ground_truth_ref": ref, "metric_name": "answer_correctness", "eval_agg_score": score}
            for ref in (ids or ["q1", "q2"])
        ],
    }


def test_compare_enforces_suite_thresholds_and_regression_tolerances():
    baseline = build_baseline(_result(score=0.8))
    assert compare_results(baseline, _result(score=0.76))["passed"] is True
    regression = compare_results(baseline, _result(score=0.7))
    assert regression["passed"] is False
    assert regression["regressions"] == ["answer_correctness"]
    suite_candidate = _result(ids=["q1", "q3"])
    suite_candidate["suite_signature"] = "changed"
    suite = compare_results(build_baseline(_result()), suite_candidate)
    assert suite["passed"] is False
    assert "ordered ground-truth refs changed" in suite["suite_change"]
    threshold = compare_results(
        build_baseline(_result(score=0.8)), _result(score=0.5, passed=False)
    )
    assert threshold["threshold_failures"]


@pytest.mark.parametrize("tolerance", [float("nan"), float("inf"), "-Infinity", -0.1])
def test_compare_rejects_invalid_default_tolerance(tolerance):
    with pytest.raises(ValueError, match="tolerance"):
        compare_results(build_baseline(_result()), _result(), tolerance)


def test_baseline_acceptance_never_accepts_failed_and_requires_force(tmp_path):
    with pytest.raises(ValueError, match="cannot become baselines"):
        build_baseline(_result(passed=False))

    target = accept_baseline(_result(), tmp_path)
    baseline = load_result(target)
    assert "results" not in baseline
    assert "git_sha" not in baseline["run_metadata"]
    with pytest.raises(FileExistsError):
        accept_baseline(_result(), tmp_path)
    assert accept_baseline(_result(), tmp_path, force=True) == target


def test_artifacts_reject_legacy_schema_and_path_traversal(tmp_path):
    legacy = _result()
    legacy.pop("schema_version")
    with pytest.raises(ValueError, match="schema_version"):
        build_baseline(legacy)

    malicious = _result()
    malicious["agent"] = "../escape"
    with pytest.raises(ValueError, match="safe artifact slug"):
        accept_baseline(malicious, tmp_path)

    malformed = _result()
    malformed["suite"] = "bad/suite"
    with pytest.raises(ValueError, match="safe artifact slug"):
        build_baseline(malformed)


def test_preview_never_connects(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config, agent_name="orders_assistant", suite_name="core", plan_payload=_plan_payload()
    )

    assert (
        run_evaluation(config, plan, apply=False, connect=lambda _: pytest.fail("connected"))
        is None
    )


class LifecycleCursor:
    def __init__(self):
        self.description = []
        self.rows = []
        self.starts = 0
        self.calls = []

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split()).upper()
        self.calls.append(normalized)
        self.rows = []
        if normalized.startswith("DESCRIBE TABLE"):
            self.rows = [("INPUT_QUERY",), ("OUTPUT",)]
        elif normalized.startswith("DESCRIBE STAGE"):
            self.rows = [("URL", "")]
        elif (
            normalized.startswith(
                "SELECT COUNT(*) FROM DB.EVAL.EVAL_ORDERS WHERE OUTPUT:GROUND_TRUTH_OUTPUT"
            )
            or "GROUND_TRUTH_INVOCATIONS" in normalized
            and normalized.startswith("SELECT COUNT(*)")
        ):
            self.rows = [(0,)]
        elif normalized == "SELECT COUNT(*) FROM DB.EVAL.EVAL_ORDERS":
            self.rows = [(1,)]
        elif normalized.startswith("SELECT INPUT_QUERY, OUTPUT:CUSTOM_CRITERIA:GROUND_TRUTH_REF"):
            self.rows = [("Revenue?", "total_revenue")]
        elif "'START'" in normalized:
            self.starts += 1
        elif "'STATUS'" in normalized:
            self.description = [
                ("RUN_NAME",),
                ("AGENT",),
                ("OTHER",),
                ("STATUS",),
                ("STATUS_DETAILS",),
            ]
            self.rows = [
                ("run", "agent", None, "FAILED", "Invocation failed")
                if self.starts == 1
                else ("run", "agent", None, "COMPLETED", "")
            ]
        elif "GET_AI_EVALUATION_DATA" in normalized:
            self.description = [
                ("RECORD_ID",),
                ("INPUT_ID",),
                ("INPUT",),
                ("METRIC_NAME",),
                ("EVAL_AGG_SCORE",),
            ]
            self.rows = [
                ("r1", "i1", "Revenue?", "answer_correctness", 0.8),
                ("r1", "i1", "Revenue?", "tool_selection_accuracy", 1.0),
            ]
        elif normalized.startswith("SELECT INPUT_QUERY"):
            self.rows = [("Revenue?", "in_scope", "total_revenue")]
        elif normalized.startswith("DESCRIBE AGENT"):
            self.description = [("aliases",)]
            self.rows = [(json.dumps({"DEFAULT": "VERSION$9", "VALIDATED": "VERSION$9"}),)]

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0]

    def close(self):
        pass


class LifecycleConnection:
    def __init__(self):
        self.cursor_value = LifecycleCursor()

    def cursor(self):
        return self.cursor_value

    def close(self):
        pass


class FailedLifecycleCursor(LifecycleCursor):
    def execute(self, sql, params=None):
        normalized = " ".join(sql.split()).upper()
        if "'STATUS'" not in normalized:
            super().execute(sql, params)
            return
        self.calls.append(normalized)
        self.description = [
            ("STATUS",),
            ("STATUS_DETAILS",),
            ("REQUEST_ID",),
            ("INFERENCE_ID",),
            ("ERROR_CODE",),
            ("OUTPUT",),
        ]
        self.rows = [
            (
                "FAILED",
                "Metric failed with private details",
                "request-1",
                "inference-1",
                399502,
                "secret",
            )
        ]


class FailedLifecycleConnection(LifecycleConnection):
    def __init__(self):
        self.cursor_value = FailedLifecycleCursor()


class PartialLifecycleCursor(LifecycleCursor):
    def execute(self, sql, params=None):
        normalized = " ".join(sql.split()).upper()
        if normalized == "SELECT COUNT(*) FROM DB.EVAL.EVAL_ORDERS":
            self.calls.append(normalized)
            self.rows = [(2,)]
            return
        if normalized.startswith("SELECT INPUT_QUERY, COALESCE"):
            self.calls.append(normalized)
            self.rows = [
                ("Revenue?", "in_scope", "q1"),
                ("Orders?", "in_scope", "q2"),
            ]
            return
        if normalized.startswith("SELECT INPUT_QUERY, OUTPUT:CUSTOM_CRITERIA:GROUND_TRUTH_REF"):
            self.calls.append(normalized)
            self.rows = [("Revenue?", "q1"), ("Orders?", "q2")]
            return
        if "'STATUS'" not in normalized and "GET_AI_EVALUATION_DATA" not in normalized:
            super().execute(sql, params)
            return
        self.calls.append(normalized)
        if "'STATUS'" in normalized:
            self.description = [
                ("RUN_NAME",),
                ("AGENT",),
                ("OTHER",),
                ("STATUS",),
                ("STATUS_DETAILS",),
            ]
            status = "INVOCATION_PARTIALLY_COMPLETED" if self.starts == 1 else "COMPLETED"
            self.rows = [("run", "agent", None, status, "")]
            return
        self.description = [
            ("RECORD_ID",),
            ("INPUT_ID",),
            ("INPUT",),
            ("METRIC_NAME",),
            ("EVAL_AGG_SCORE",),
        ]
        self.rows = [
            ("r1", "i1", "Revenue?", "answer_correctness", 0.8),
            ("r1", "i1", "Revenue?", "tool_selection_accuracy", 1.0),
        ]
        if self.starts > 1:
            self.rows.extend(
                [
                    ("r2", "i2", "Orders?", "answer_correctness", 0.9),
                    ("r2", "i2", "Orders?", "tool_selection_accuracy", 1.0),
                ]
            )


class PartialLifecycleConnection(LifecycleConnection):
    def __init__(self):
        self.cursor_value = PartialLifecycleCursor()


def test_evaluation_cleanup_only_failure_closes_both_and_preserves_written_candidate(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )
    closed = []

    class Cursor(LifecycleCursor):
        def close(self):
            closed.append("cursor")
            raise OSError("cursor close")

    class Connection(LifecycleConnection):
        def __init__(self):
            self.cursor_value = Cursor()

        def close(self):
            closed.append("connection")
            raise OSError("connection close")

    with pytest.raises(OSError, match="cursor close") as failure:
        run_evaluation(
            config,
            plan,
            apply=True,
            run_name="cleanup_run",
            poll_attempts=1,
            poll_interval=0,
            transient_retries=1,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: Connection(),
            sleep=lambda _: None,
        )
    assert closed == ["cursor", "connection"]
    assert [str(error) for error in failure.value.cleanup_errors] == ["connection close"]
    candidates = list(config.artifact_dir.glob("candidates/**/*.json"))
    assert len(candidates) == 1
    assert load_result(candidates[0])["passed"] is True


def test_apply_retries_once_and_persists_candidate(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )
    connection = LifecycleConnection()

    output = run_evaluation(
        config,
        plan,
        apply=True,
        run_name="candidate_run",
        poll_attempts=1,
        poll_interval=0,
        transient_retries=1,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        connect=lambda _: connection,
        sleep=lambda _: None,
    )

    assert connection.cursor_value.starts == 2
    assert connection.cursor_value.calls[:4] == [
        "USE ROLE EVAL_ROLE",
        "USE WAREHOUSE WH",
        "USE DATABASE DB",
        "USE SCHEMA EVAL_RESULTS",
    ]
    candidate = load_result(output)
    assert candidate["run_name"] == "candidate_run_r1"
    assert candidate["run_metadata"]["evaluated_version"] == "VERSION$9"
    assert candidate["run_metadata"]["plan_identity"]["agent_fqn"] == plan.agent_fqn
    assert "projection" not in candidate
    assert candidate["ordered_ground_truth_refs"] == ["total_revenue"]
    assert output.parent.name == "core"


def test_apply_retries_partial_completion_under_new_run_name(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(),
    )
    connection = PartialLifecycleConnection()

    output = run_evaluation(
        config,
        plan,
        apply=True,
        run_name="partial_run",
        poll_attempts=1,
        poll_interval=0,
        transient_retries=1,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        connect=lambda _: connection,
        sleep=lambda _: None,
    )

    assert connection.cursor_value.starts == 2
    candidate = load_result(output)
    assert candidate["run_name"] == "partial_run_r1"
    assert candidate["total_records"] == 2


def test_partial_completion_failure_records_cardinality(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(),
    )

    with pytest.raises(RuntimeError, match="ended in TIMEOUT"):
        run_evaluation(
            config,
            plan,
            apply=True,
            run_name="partial_failure",
            poll_attempts=1,
            poll_interval=0,
            transient_retries=0,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: PartialLifecycleConnection(),
            sleep=lambda _: None,
        )

    path = (
        config.artifact_dir
        / "diagnostics"
        / "sandbox"
        / "DB"
        / "AGENT_SCHEMA"
        / "ORDERS_ASSISTANT"
        / "core"
        / "partial_failure.json"
    )
    diagnostic = json.loads(path.read_text())
    assert diagnostic["status"] == "TIMEOUT"
    assert diagnostic["observed_status"] == "INVOCATION_PARTIALLY_COMPLETED"
    assert diagnostic["expected_records"] == 2
    assert diagnostic["actual_records"] == 1
    assert diagnostic["error"]["category"] == "transient_platform_failure"


def test_terminal_failure_writes_whitelist_only_diagnostic(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )

    with pytest.raises(RuntimeError, match="ended in FAILED") as exc_info:
        run_evaluation(
            config,
            plan,
            apply=True,
            run_name="failed_run",
            poll_attempts=1,
            poll_interval=0,
            transient_retries=0,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: FailedLifecycleConnection(),
            sleep=lambda _: None,
        )

    path = (
        config.artifact_dir
        / "diagnostics"
        / "sandbox"
        / "DB"
        / "AGENT_SCHEMA"
        / "ORDERS_ASSISTANT"
        / "core"
        / "failed_run.json"
    )
    diagnostic = json.loads(path.read_text())
    assert diagnostic == {
        "agent": "orders_assistant",
        "agent_fqn": "DB.AGENT_SCHEMA.ORDERS_ASSISTANT",
        "artifact_type": "evaluation_diagnostic",
        "error": {"category": "terminal_evaluation_failure", "code": "399502"},
        "inference_ids": ["inference-1"],
        "plan_identity": plan.plan_identity,
        "request_ids": ["request-1"],
        "run_name": "failed_run",
        "schema_version": 1,
        "status": "FAILED",
        "suite": "core",
    }
    assert "private" not in path.read_text().lower()
    assert "secret" not in path.read_text().lower()
    assert "private" not in str(exc_info.value).lower()


def test_apply_rejects_unallowlisted_plan_before_connector_use(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(),
    )

    with pytest.raises(ValueError, match="allowed targets"):
        run_evaluation(
            config,
            plan,
            apply=True,
            allowed_targets=[],
            allowed_databases=["DB"],
            connect=lambda _: pytest.fail("connector used before allowlist validation"),
        )
    with pytest.raises(ValueError, match="allowed databases"):
        run_evaluation(
            config,
            plan,
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=[],
            connect=lambda _: pytest.fail("connector used before allowlist validation"),
        )


def test_compare_rejects_candidate_tolerance_widening():
    baseline = build_baseline(_result(score=0.8))
    candidate = _result(score=0.7)
    candidate["regression_tolerances"] = {"answer_correctness": 0.2}
    result = compare_results(baseline, candidate)
    assert result["passed"] is False
    assert result["suite_change"] == "regression tolerance policy changed"


def test_candidate_is_indeterminate_when_default_changes(tmp_path):
    plan = build_plan(
        _config(tmp_path, _manifest()),
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(),
    )
    candidate = build_candidate(
        plan=plan,
        run_name="run",
        rows=_rows(),
        provenance={
            "agent_fqn": plan.agent_fqn,
            "evaluated_version": "VERSION$7",
            "plan_identity": plan.plan_identity,
            "pre_start": {"default_version": "VERSION$7", "aliases": {}},
            "post_completion": {"default_version": "VERSION$8", "aliases": {}},
            "default_version_changed": True,
        },
    )
    assert candidate["passed"] is False
    assert candidate["status"] == "indeterminate"
    assert "DEFAULT version changed" in candidate["threshold_failures"][-1]


def test_apply_fails_before_upload_when_agent_missing_or_has_no_default(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )

    class MissingAgentCursor(LifecycleCursor):
        def execute(self, sql, params=None):
            if "DESCRIBE AGENT" in " ".join(sql.split()).upper():
                raise RuntimeError("does not exist")
            super().execute(sql, params)

    connection = LifecycleConnection()
    connection.cursor_value = MissingAgentCursor()
    with pytest.raises(RuntimeError, match="requires existing Agent"):
        run_evaluation(
            config,
            plan,
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: connection,
            sleep=lambda _: None,
        )
    assert not any(
        "CREATE STAGE" in call or "'START'" in call for call in connection.cursor_value.calls
    )


def test_apply_treats_empty_describe_result_as_missing_agent(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )

    class EmptyDescribeCursor(LifecycleCursor):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "DESCRIBE AGENT" in " ".join(sql.split()).upper():
                self.rows = []

        def fetchone(self):
            return self.rows[0] if self.rows else None

    connection = LifecycleConnection()
    connection.cursor_value = EmptyDescribeCursor()
    with pytest.raises(RuntimeError, match="requires existing Agent"):
        run_evaluation(
            config,
            plan,
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: connection,
            sleep=lambda _: None,
        )
    assert not any(
        "CREATE STAGE" in call or "'START'" in call for call in connection.cursor_value.calls
    )


def test_apply_fails_when_default_changes_before_start(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )

    class VersionChangeCursor(LifecycleCursor):
        def __init__(self):
            super().__init__()
            self.describe_count = 0

        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "DESCRIBE AGENT" in " ".join(sql.split()).upper():
                self.describe_count += 1
                version = "VERSION$9" if self.describe_count == 1 else "VERSION$10"
                self.rows = [(json.dumps({"DEFAULT": version}),)]

    connection = LifecycleConnection()
    connection.cursor_value = VersionChangeCursor()
    with pytest.raises(RuntimeError, match="changed before evaluation START"):
        run_evaluation(
            config,
            plan,
            apply=True,
            run_name="drift",
            poll_attempts=1,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: connection,
            sleep=lambda _: None,
        )
    assert not any("'START'" in call for call in connection.cursor_value.calls)


def test_table_validation_rejects_duplicate_refs_and_inputs():
    class Cursor:
        def __init__(self, identity_rows):
            self.identity_rows = identity_rows
            self.rows = []

        def execute(self, sql):
            normalized = " ".join(sql.split()).upper()
            if normalized.startswith("DESCRIBE TABLE"):
                self.rows = [("INPUT_QUERY",), ("OUTPUT",)]
            elif normalized.startswith("SELECT COUNT(*)"):
                self.rows = [(2,)]
            elif normalized.startswith("SELECT INPUT_QUERY, COALESCE"):
                self.rows = self.identity_rows

        def fetchall(self):
            return self.rows

        def fetchone(self):
            return self.rows[0]

    with pytest.raises(ValueError, match="duplicate ground_truth_ref"):
        validate_table(
            Cursor([("one", "in_scope", "q1"), ("two", "in_scope", "q1")]),
            "DB.S.T",
            ["logical_consistency"],
            ["q1", "q2"],
        )
    with pytest.raises(ValueError, match="duplicate INPUT_QUERY"):
        validate_table(
            Cursor([("same", "in_scope", "q1"), ("same", "in_scope", "q2")]),
            "DB.S.T",
            ["logical_consistency"],
            ["q1", "q2"],
        )


@pytest.mark.parametrize(
    "status,passed",
    [
        ("indeterminate", False),
        ("failed", True),
        ("running", True),
        ("completed", False),
        ("completed", None),
        ("completed", "true"),
        ("completed", 1),
    ],
)
def test_ineligible_candidates_cannot_compare_gate_or_be_accepted(tmp_path, status, passed):
    baseline = build_baseline(_result())
    candidate = _result(passed=passed)
    candidate["status"] = status
    if status == "indeterminate":
        candidate["run_metadata"]["post_completion"]["default_version"] = "VERSION$2"
        candidate["run_metadata"]["default_version_changed"] = True
    comparison = compare_results(baseline, candidate)
    assert comparison["passed"] is False
    assert comparison["eligibility_failures"]["candidate"]
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    baseline_path.write_text(json.dumps(baseline))
    candidate_path.write_text(json.dumps(candidate))
    assert gate_candidate(candidate_path, baseline=baseline_path)["passed"] is False
    with pytest.raises(ValueError, match="cannot become baselines"):
        accept_baseline(candidate, tmp_path / "accepted")
    assert not (tmp_path / "accepted").exists()


@pytest.mark.parametrize(
    "damage",
    [
        "null",
        "duplicate",
        "nan",
        "inf",
        "missing",
        "unknown_ref",
        "unknown_metric",
        "summary",
        "count",
        "total",
        "no_rows",
    ],
)
def test_compare_and_gate_reject_invalid_evidence(tmp_path, damage):
    baseline = build_baseline(_result())
    candidate = _result()
    if damage in {"null", "nan", "inf"}:
        candidate["results"][0]["eval_agg_score"] = {
            "null": None,
            "nan": float("nan"),
            "inf": float("inf"),
        }[damage]
    elif damage == "duplicate":
        candidate["results"].append({**candidate["results"][0], "record_id": "different-id"})
    elif damage == "missing":
        candidate["results"].pop()
    elif damage == "unknown_ref":
        candidate["results"][0]["ground_truth_ref"] = "unexpected"
    elif damage == "unknown_metric":
        candidate["results"][0]["metric_name"] = "unexpected"
    elif damage == "summary":
        candidate["summary"]["answer_correctness"]["avg"] = float("nan")
    elif damage == "count":
        candidate["summary"]["answer_correctness"]["n"] = 1
    elif damage == "total":
        candidate["total_records"] = float("inf")
    else:
        candidate.pop("results")
    with pytest.raises(ValueError):
        compare_results(baseline, candidate)
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    baseline_path.write_text(json.dumps(baseline))
    candidate_path.write_text(json.dumps(candidate))
    with pytest.raises(ValueError):
        gate_candidate(candidate_path, baseline=baseline_path)


@pytest.mark.parametrize("policy", ["thresholds", "regression_tolerances"])
def test_unknown_signed_policy_fails_plan_and_pre_connector_apply(tmp_path, policy):
    config = _config(tmp_path, _manifest())
    payload = _plan_payload()
    payload[policy]["typo_metric"] = 0.1
    signed = json.loads(payload["signature_material"])
    signed[policy] = payload[policy]
    payload["signature_material"] = json.dumps(signed, separators=(",", ":"))
    payload["suite_signature"] = hashlib.md5(payload["signature_material"].encode()).hexdigest()
    with pytest.raises(ValueError, match="undeclared metrics: typo_metric"):
        build_plan(config, agent_name="orders_assistant", suite_name="core", plan_payload=payload)
    plan = build_plan(
        config, agent_name="orders_assistant", suite_name="core", plan_payload=_plan_payload()
    )
    invalid = replace(plan, **{policy: {"typo_metric": 0.1}})
    with pytest.raises(ValueError, match="undeclared metrics: typo_metric"):
        run_evaluation(
            config,
            invalid,
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: pytest.fail("connected before policy validation"),
        )


@pytest.mark.parametrize("excluded_score", [None, float("nan"), float("inf"), "absent"])
def test_boundary_exclusions_preserve_completeness_and_observation_grain(tmp_path, excluded_score):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config, agent_name="orders_assistant", suite_name="core", plan_payload=_plan_payload()
    )
    rows = _rows()
    if excluded_score == "absent":
        rows.pop()
    else:
        rows[-1]["eval_agg_score"] = excluded_score
    for index, row in enumerate(rows):
        row["record_id"] = f"metric-record-{index}"
        row["input_id"] = f"metric-input-{index}"
    candidate = build_candidate(
        plan=plan,
        run_name="boundary",
        rows=rows,
        provenance={**_result()["run_metadata"], "plan_identity": plan.plan_identity},
    )
    assert candidate["total_records"] == 2
    assert candidate["summary"]["tool_selection_accuracy"] == {"avg": 1.0, "n": 1}
    baseline = build_baseline(candidate)
    assert compare_results(baseline, candidate)["passed"] is True
    path = write_candidate(candidate, tmp_path / "artifacts")
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(json.dumps(baseline))
    assert gate_candidate(path, baseline=baseline_file)["passed"] is True


@pytest.mark.parametrize("damage", ["null", "duplicate", "nan", "inf", "missing"])
def test_native_run_rejects_invalid_observations_without_candidate(tmp_path, damage):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )

    class InvalidRowsCursor(LifecycleCursor):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "GET_AI_EVALUATION_DATA" not in sql:
                return
            if damage in {"null", "nan", "inf"}:
                score = {"null": None, "nan": float("nan"), "inf": float("inf")}[damage]
                self.rows[0] = (*self.rows[0][:-1], score)
            elif damage == "duplicate":
                self.rows.append(("r-other", "i-other", *self.rows[0][2:]))
            else:
                self.rows.pop()

    connection = LifecycleConnection()
    connection.cursor_value = InvalidRowsCursor()
    connection.cursor_value.starts = 1
    with pytest.raises(RuntimeError, match="INCOMPLETE_RESULTS"):
        run_evaluation(
            config,
            plan,
            apply=True,
            run_name="invalid",
            poll_attempts=1,
            poll_interval=0,
            transient_retries=0,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: connection,
            sleep=lambda _: None,
        )
    assert not (config.artifact_dir / "candidates").exists()
    diagnostic = next((config.artifact_dir / "diagnostics").rglob("invalid.json"))
    assert json.loads(diagnostic.read_text())["status"] == "INCOMPLETE_RESULTS"


@pytest.mark.parametrize("excluded_score", [None, float("nan"), "absent"])
def test_native_fetch_annotates_boundaries_before_completeness(tmp_path, excluded_score):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config, agent_name="orders_assistant", suite_name="core", plan_payload=_plan_payload()
    )

    class BoundaryCursor(PartialLifecycleCursor):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if sql.startswith("SELECT input_query, COALESCE"):
                self.rows[1] = ("Orders?", "out_of_scope", "q2")
            elif "GET_AI_EVALUATION_DATA" in sql:
                if excluded_score == "absent":
                    self.rows.pop()
                else:
                    self.rows[-1] = (*self.rows[-1][:-1], excluded_score)

    connection = LifecycleConnection()
    connection.cursor_value = BoundaryCursor()
    connection.cursor_value.starts = 1
    path = run_evaluation(
        config,
        plan,
        apply=True,
        run_name="boundary",
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        connect=lambda _: connection,
        sleep=lambda _: None,
    )
    candidate = load_result(path)
    assert candidate["passed"] is True
    assert candidate["summary"]["tool_selection_accuracy"]["n"] == 1
    assert compare_results(build_baseline(candidate), candidate)["passed"] is True


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate_excluded",
        "inconsistent_type",
        "boundary_answer",
        "missing_in_scope_tool",
        "boolean_score",
        "summary_mismatch",
    ],
)
def test_boundary_exclusion_cannot_hide_invalid_observations(tmp_path, damage):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config, agent_name="orders_assistant", suite_name="core", plan_payload=_plan_payload()
    )
    valid = build_candidate(
        plan=plan,
        run_name="valid",
        rows=_rows(),
        provenance={**_result()["run_metadata"], "plan_identity": plan.plan_identity},
    )
    baseline = build_baseline(valid)
    if damage == "duplicate_excluded":
        valid["results"].append(dict(valid["results"][-1]))
    elif damage == "inconsistent_type":
        valid["results"][-1]["test_type"] = "in_scope"
    elif damage == "boundary_answer":
        valid["results"][1]["eval_agg_score"] = None
    elif damage == "missing_in_scope_tool":
        valid["results"].pop(2)
    elif damage == "boolean_score":
        valid["results"][0]["eval_agg_score"] = True
    else:
        valid["summary"]["answer_correctness"]["avg"] = 0.9
    with pytest.raises(ValueError):
        compare_results(baseline, valid)


@pytest.mark.parametrize("policy", ["thresholds", "regression_tolerances"])
def test_entirely_excluded_tool_cannot_satisfy_policy(tmp_path, policy):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config, agent_name="orders_assistant", suite_name="core", plan_payload=_plan_payload()
    )
    plan = replace(plan, thresholds={}, regression_tolerances={})
    plan = replace(plan, **{policy: {"tool_selection_accuracy": 0.0}})
    rows = _rows()
    for row in rows:
        row["test_type"] = "out_of_scope"
    candidate = build_candidate(
        plan=plan,
        run_name="excluded",
        rows=rows,
        provenance={**_result()["run_metadata"], "plan_identity": plan.plan_identity},
    )
    assert candidate["passed"] is False
    assert "missing" in candidate["threshold_failures"][0]
    candidate["passed"] = True
    with pytest.raises(ValueError, match="cannot become baselines"):
        build_baseline(candidate)


@pytest.mark.parametrize("field,value", [("status", "failed"), ("passed", False)])
def test_ineligible_baseline_never_authorizes_comparison(field, value):
    baseline = build_baseline(_result())
    baseline[field] = value
    comparison = compare_results(baseline, _result())
    assert comparison["passed"] is False
    assert comparison["eligibility_failures"]["baseline"]


@pytest.mark.parametrize("field", ["avg", "n"])
@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), True])
@pytest.mark.parametrize("side", ["baseline", "candidate"])
def test_compare_rejects_invalid_summary_statistics(field, invalid, side):
    baseline = build_baseline(_result())
    candidate = _result()
    artifact = baseline if side == "baseline" else candidate
    artifact["summary"]["answer_correctness"][field] = invalid
    with pytest.raises(ValueError):
        compare_results(baseline, candidate)


@pytest.mark.parametrize("metric", ["tool_selection_accuracy", "tool_execution_accuracy"])
@pytest.mark.parametrize("phase", ["start", "status", "fetch", "fetch_retry"])
def test_source_rebuild_cannot_exclude_originally_in_scope_failure(tmp_path, metric, phase):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config, agent_name="orders_assistant", suite_name="core", plan_payload=_plan_payload()
    )
    plan = replace(
        plan,
        metric_names=["answer_correctness", metric],
        thresholds={metric: 0.8},
        regression_tolerances={metric: 0.05},
    )

    class RebuiltCursor(PartialLifecycleCursor):
        def __init__(self):
            super().__init__()
            self.changed = False
            self.fetches = 0

        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "'START'" in sql and phase == "start":
                self.changed = True
            if "'STATUS'" in sql:
                self.rows = [("run", "agent", None, "COMPLETED", "")]
                if phase == "status":
                    self.changed = True
            if "GET_AI_EVALUATION_DATA" in sql:
                self.fetches += 1
                self.rows = [
                    ("r1", "i1", "Revenue?", "answer_correctness", 1.0),
                    ("r1", "i1", "Revenue?", metric, 1.0),
                    ("r2", "i2", "Orders?", "answer_correctness", 1.0),
                    ("r2", "i2", "Orders?", metric, 0.0),
                ]
                if phase in {"fetch", "fetch_retry"}:
                    self.changed = True
                if phase == "fetch_retry" and self.fetches == 1:
                    self.rows.pop()
            if sql.startswith("SELECT input_query, COALESCE") and self.changed:
                self.rows[1] = ("Orders?", "out_of_scope", "q2")

    connection = LifecycleConnection()
    cursor = connection.cursor_value = RebuiltCursor()
    path = run_evaluation(
        config,
        plan,
        apply=True,
        run_name="rebuild",
        poll_attempts=1,
        poll_interval=0,
        transient_retries=1,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        connect=lambda _: connection,
        sleep=lambda _: None,
    )
    candidate = load_result(path)
    assert cursor.starts == 1
    assert cursor.fetches == (2 if phase == "fetch_retry" else 1)
    assert candidate["summary"][metric] == {"avg": 0.5, "n": 2}
    assert candidate["results"][-1]["test_type"] == "in_scope"
    assert candidate["results"][-1]["eval_agg_score"] == 0.0
    assert candidate["run_metadata"]["dataset_snapshot"] == [
        ["Orders?", "in_scope", "q2"],
        ["Revenue?", "in_scope", "q1"],
    ]
    assert candidate["run_metadata"]["dataset_source_changed"] is True
    assert candidate["status"] == "indeterminate"
    assert candidate["passed"] is False
    baseline_candidate = json.loads(json.dumps(candidate))
    baseline_candidate["run_metadata"]["dataset_source_changed"] = False
    baseline_candidate["status"] = "completed"
    baseline_candidate["passed"] = True
    baseline_candidate["threshold_failures"] = []
    for row in baseline_candidate["results"]:
        row["eval_agg_score"] = 1.0
    baseline_candidate["summary"] = compute_summary(baseline_candidate["results"])
    baseline_path = accept_baseline(baseline_candidate, tmp_path / "baselines")
    assert gate_candidate(path, baseline=baseline_path)["passed"] is False
    with pytest.raises(ValueError, match="cannot become baselines"):
        build_baseline(candidate)


@pytest.mark.parametrize("phase", ["validation", "upload", "retry_upload"])
def test_source_drift_blocks_start_without_rebinding(tmp_path, phase):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )

    class Cursor(LifecycleCursor):
        def __init__(self):
            super().__init__()
            self.changed = False

        def execute(self, sql, params=None):
            super().execute(sql, params)
            if phase == "validation" and "WHERE output:ground_truth_output" in sql:
                self.changed = True
            if sql.startswith("COPY INTO") and (
                phase == "upload" or phase == "retry_upload" and self.starts == 1
            ):
                self.changed = True
            if sql.startswith("SELECT input_query, COALESCE") and self.changed:
                self.rows = [("Revenue?", "out_of_scope", "total_revenue")]

    connection = LifecycleConnection()
    cursor = connection.cursor_value = Cursor()
    with pytest.raises(RuntimeError, match="source changed before evaluation START"):
        run_evaluation(
            config,
            plan,
            apply=True,
            run_name="pre_start_rebuild",
            poll_attempts=1,
            poll_interval=0,
            transient_retries=1,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: connection,
            sleep=lambda _: None,
        )
    assert cursor.starts == (1 if phase == "retry_upload" else 0)
    assert not (config.artifact_dir / "candidates").exists()


def test_source_drift_after_failed_run_stops_transient_retry(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )

    class Cursor(LifecycleCursor):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if sql.startswith("SELECT input_query, COALESCE") and self.starts:
                self.rows = [("Revenue?", "out_of_scope", "total_revenue")]

    connection = LifecycleConnection()
    cursor = connection.cursor_value = Cursor()
    with pytest.raises(RuntimeError, match="DATASET_SOURCE_CHANGED"):
        run_evaluation(
            config,
            plan,
            apply=True,
            run_name="failed_rebuild",
            poll_attempts=1,
            poll_interval=0,
            transient_retries=1,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: connection,
            sleep=lambda _: None,
        )
    assert cursor.starts == 1
    assert not (config.artifact_dir / "candidates").exists()
    diagnostic = next(config.artifact_dir.glob("diagnostics/**/*.json"))
    assert json.loads(diagnostic.read_text())["status"] == "DATASET_SOURCE_CHANGED"


@pytest.mark.parametrize(
    "source_rows",
    [
        [],
        [(None, "in_scope", "q1")],
        [(" ", "in_scope", "q1")],
        [("Question?", "in_scope", None)],
        [("Question?", "in_scope", "")],
        [("Question?", "", "q1")],
        [("Question?", None, "q1")],
        [("Question?", "in_scope", "q2")],
        [("Question?", "in_scope", "q1"), ("Question?", "negative", "q2")],
        [("One?", "in_scope", "q1"), ("Two?", "negative", "q1")],
    ],
)
def test_snapshot_rejects_invalid_mapping(source_rows):
    with pytest.raises(ValueError):
        validate_snapshot(source_rows, ["q1"])


def test_snapshot_is_immutable_order_independent_and_requires_known_result_input():
    source = [["Revenue?", "in_scope", "q1"], ["Orders?", "negative", "q2"]]
    snapshot = validate_snapshot(source, ["q1", "q2"])
    assert snapshot == validate_snapshot(list(reversed(source)), ["q1", "q2"])
    source[0][1] = "out_of_scope"
    rows = [{"input": "Revenue?"}]
    annotate_rows(snapshot, rows)
    assert rows == [{"input": "Revenue?", "test_type": "in_scope", "ground_truth_ref": "q1"}]
    for invalid in ("Unknown?", None, []):
        with pytest.raises(ValueError, match="absent from the dataset snapshot"):
            annotate_rows(snapshot, [{"input": invalid}])


@pytest.mark.parametrize("damage", ["type", "ref", "input", "snapshot", "drift_flag", "drift"])
def test_candidate_snapshot_binding_rejects_inconsistent_evidence(tmp_path, damage):
    candidate = _result()
    for row in candidate["results"]:
        row["input"] = row["ground_truth_ref"] + "?"
        row["test_type"] = "in_scope"
    candidate["run_metadata"].update(
        dataset_snapshot=[["q1?", "in_scope", "q1"], ["q2?", "in_scope", "q2"]],
        dataset_source_changed=False,
    )
    baseline = build_baseline(candidate)
    assert (
        baseline["run_metadata"]["dataset_snapshot"]
        == candidate["run_metadata"]["dataset_snapshot"]
    )
    assert "results" not in baseline
    if damage == "type":
        candidate["results"][0]["test_type"] = "out_of_scope"
    elif damage == "ref":
        candidate["results"][0]["ground_truth_ref"] = "q2"
    elif damage == "input":
        candidate["results"][0]["input"] = "unknown"
    elif damage == "snapshot":
        candidate["run_metadata"]["dataset_snapshot"].pop()
    elif damage == "drift_flag":
        candidate["run_metadata"].pop("dataset_source_changed")
    else:
        candidate["run_metadata"]["dataset_source_changed"] = True
    with pytest.raises(ValueError):
        write_candidate(candidate, tmp_path)


def test_legacy_candidate_without_snapshot_keeps_existing_validation(tmp_path):
    path = write_candidate(_result(), tmp_path)
    candidate = load_result(path)
    assert "dataset_snapshot" not in candidate["run_metadata"]
    baseline_path = accept_baseline(candidate, tmp_path / "baselines")
    assert gate_candidate(path, baseline=baseline_path)["passed"] is True


def test_source_count_drift_fails_validation_before_upload_or_start(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )

    class Cursor(LifecycleCursor):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if sql == "SELECT COUNT(*) FROM DB.EVAL.EVAL_ORDERS":
                self.rows = [(2,)]

    connection = LifecycleConnection()
    cursor = connection.cursor_value = Cursor()
    with pytest.raises(ValueError, match="cardinality changed during validation"):
        run_evaluation(
            config,
            plan,
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: connection,
            sleep=lambda _: None,
        )
    assert cursor.starts == 0
    assert not any(call.startswith("COPY INTO") for call in cursor.calls)


@pytest.mark.parametrize("damage", ["empty", "duplicate", "missing_ref", "changed_input"])
def test_invalid_source_after_start_retains_original_binding_and_fails(tmp_path, damage):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config,
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )

    class Cursor(LifecycleCursor):
        def __init__(self):
            super().__init__()
            self.completed = False

        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "'STATUS'" in sql:
                self.rows = [("run", "agent", None, "COMPLETED", "")]
                self.completed = True
            if sql.startswith("SELECT input_query, COALESCE") and self.completed:
                if damage == "empty":
                    self.rows = []
                elif damage == "duplicate":
                    self.rows *= 2
                elif damage == "missing_ref":
                    self.rows = [("Revenue?", "in_scope", None)]
                else:
                    self.rows = [("Changed?", "in_scope", "total_revenue")]

    connection = LifecycleConnection()
    cursor = connection.cursor_value = Cursor()
    path = run_evaluation(
        config,
        plan,
        apply=True,
        run_name="invalid_source",
        poll_attempts=1,
        poll_interval=0,
        transient_retries=1,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        connect=lambda _: connection,
        sleep=lambda _: None,
    )
    candidate = load_result(path)
    assert cursor.starts == 1
    assert candidate["status"] == "indeterminate"
    assert candidate["passed"] is False
    assert candidate["run_metadata"]["dataset_snapshot"] == [
        ["Revenue?", "in_scope", "total_revenue"]
    ]
    assert candidate["results"][0]["ground_truth_ref"] == "total_revenue"
