from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import builtins
from argparse import Namespace

import pytest

from dbt_cortex_agent.artifacts import ARTIFACT_SCHEMA_VERSION
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.eval.baseline import (
    accept_baseline,
    build_baseline,
    build_migrated_baseline,
    migrate_legacy_baseline,
)
from dbt_cortex_agent.eval.compare import compare_results
from dbt_cortex_agent.eval.dataset import validate_eval_meta, validate_table
from dbt_cortex_agent.eval.lifecycle import (
    TERMINAL_SUCCESS,
    build_plan,
    flatten_status_details,
    _fetch_rows,
    is_retryable,
    poll,
    run_evaluation,
    _default_connect,
)
from dbt_cortex_agent.eval.results import build_candidate, compute_summary, load_result


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
                "config": {"meta": {"cortex_agent": {
                    "enabled": True,
                    "snowflake_name": "ORDERS_ASSISTANT",
                    "naming": {"sandbox_eval": "ORDERS_ASSISTANT_SANDBOX_EVAL"},
                }}},
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
            project_dir=str(tmp_path), manifest=None, target="sandbox", connection="conn",
            database="DB", schema="AGENT_SCHEMA", role="ROLE", warehouse="WH",
            artifact_dir="artifacts", dbt_executable=None, snow_executable=None,
        ),
        env={},
    )


def _plan_payload(*, refs=None, tolerances=None):
    token = "__DBT_CORTEX_AGENT_DATASET_NAME__"
    identity = {
        "agent_name": "orders_assistant", "suite_name": "core",
        "eval_model": "eval_orders",
        "agent_fqn": "DB.AGENT_SCHEMA.ORDERS_ASSISTANT",
        "dataset_fqn": "DB.EVAL.EVAL_ORDERS", "stage_fqn": "DB.AGENT_SCHEMA.EVAL_CONFIG_STAGE",
        "target_name": "sandbox", "target_role": "EVAL_ROLE",
        "target_database": "DB", "target_schema": "AGENT_SCHEMA",
        "target_warehouse": "WH",
    }
    native = {
        "dataset": {"dataset_type": "CORTEX AGENT", "table_name": identity["dataset_fqn"], "dataset_name": token,
                    "column_mapping": {"query_text": "INPUT_QUERY", "ground_truth": "OUTPUT"}},
        "evaluation": {"agent_params": {"agent_name": identity["agent_fqn"], "agent_type": "CORTEX AGENT"},
                       "run_params": {"label": "orders_assistant/core", "description": "Core suite"},
                       "source_metadata": {"type": "dataset", "dataset_name": token}},
        "metrics": ["answer_correctness", "tool_selection_accuracy"],
    }
    payload = {
        "schema_version": 1, "identity": identity, "native_eval_config": native,
        "dataset_name_token": token, "config_filename_template": "eval_orders__RUN_NAME__.json",
        "metric_names": ["answer_correctness", "tool_selection_accuracy"],
        "thresholds": {"answer_correctness": 0.6, "tool_selection_accuracy": 0.8},
        "regression_tolerances": tolerances or {"tool_selection_accuracy": 0.05},
        "ordered_ground_truth_refs": refs or ["q1", "q2"],
    }
    signed = {
        "plan_schema_version": payload["schema_version"], "identity": identity,
        "native_eval_config": native, "metric_names": payload["metric_names"],
        "thresholds": payload["thresholds"], "regression_tolerances": payload["regression_tolerances"],
        "ordered_ground_truth_refs": payload["ordered_ground_truth_refs"],
    }
    payload["signature_material"] = json.dumps(signed, separators=(",", ":"))
    payload["suite_signature"] = hashlib.md5(payload["signature_material"].encode()).hexdigest()
    return payload


def test_build_plan_consumes_dbt_payload_without_reconstructing_identity(tmp_path):
    plan = build_plan(
        _config(tmp_path, _manifest()), agent_name="orders_assistant", suite_name="core",
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
                if "run-operation" in command else ""
            )
            return subprocess.CompletedProcess(command, 0, stdout, "")

    fake = FakeRunner()
    build_plan(
        _config(tmp_path, _manifest()), agent_name="orders_assistant", suite_name="core",
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
                if "run-operation" in command else ""
            )
            return subprocess.CompletedProcess(command, 0, stdout, "")

    config = _config(tmp_path, _manifest())
    context = type("Context", (), {"dbt_env": {"SNOWFLAKE_ACCOUNT": "acct"}})()
    config = __import__("dataclasses").replace(config, execution_context=context)
    fake = FakeRunner()

    build_plan(
        config, agent_name="orders_assistant", suite_name="core", runner=fake
    )

    assert fake.envs == [
        {"SNOWFLAKE_ACCOUNT": "acct"},
        {"SNOWFLAKE_ACCOUNT": "acct"},
    ]


def test_build_plan_fails_closed_for_tampered_or_duplicate_refs(tmp_path):
    payload = _plan_payload()
    payload["identity"]["agent_fqn"] = "DB.AGENT_SCHEMA.WRONG"
    with pytest.raises(ValueError, match="signed fields"):
        build_plan(
            _config(tmp_path, _manifest()), agent_name="orders_assistant", suite_name="core",
            plan_payload=payload,
        )
    with pytest.raises(ValueError, match="non-empty and unique"):
        build_plan(
            _config(tmp_path / "duplicate", _manifest()), agent_name="orders_assistant",
            suite_name="core", plan_payload=_plan_payload(refs=["q1", "q1"]),
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
    projection["suite_signature"] = hashlib.md5(projection["signature_material"].encode()).hexdigest()
    with pytest.raises(ValueError, match="must not contain projection"):
        build_plan(
            _config(tmp_path, _manifest()), agent_name="orders_assistant",
            suite_name="core", plan_payload=projection,
        )

    mismatch = _plan_payload()
    mismatch["native_eval_config"]["evaluation"]["agent_params"]["agent_name"] = "DB.S.WRONG"
    signed = json.loads(mismatch["signature_material"])
    signed["native_eval_config"] = mismatch["native_eval_config"]
    mismatch["signature_material"] = json.dumps(signed, separators=(",", ":"))
    mismatch["suite_signature"] = hashlib.md5(mismatch["signature_material"].encode()).hexdigest()
    with pytest.raises(ValueError, match="native config Agent must match"):
        build_plan(
            _config(tmp_path / "mismatch", _manifest()), agent_name="orders_assistant",
            suite_name="core", plan_payload=mismatch,
        )


def test_metric_validation_fails_before_execution():
    with pytest.raises(ValueError, match="undeclared metrics"):
        validate_eval_meta({"metrics": ["answer_correctness"], "thresholds": {"missing": 0.5}})
    with pytest.raises(ValueError, match="requires a prompt"):
        validate_eval_meta({"metrics": [{"name": "quality"}]})
    with pytest.raises(ValueError, match="must define all three"):
        validate_eval_meta({"metrics": [{"name": "quality", "prompt": "score", "score_ranges": {"min_score": [1, 3]}}]})


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
    cursor = PollCursor([
        ("INVOCATION_COMPLETED", ""), ("COMPUTATION_IN_PROGRESS", ""), ("COMPLETED", "")
    ])
    sleeps = []
    result = poll(cursor, "run", "@stage/config", attempts=5, interval=2, sleep=sleeps.append)
    assert result.status in TERMINAL_SUCCESS
    assert cursor.calls == 3
    assert sleeps == [2, 2]

    timeout = poll(
        PollCursor([("CREATED", ""), ("INVOCATION_IN_PROGRESS", "")]),
        "run", "@stage/config", attempts=2, interval=0, sleep=lambda _: None,
    )
    assert timeout.status == "TIMEOUT"


def test_status_detail_classification_handles_json_and_is_bounded():
    assert flatten_status_details('["Invocation failed", "rate limit"]') == "Invocation failed; rate limit"
    assert is_retryable('["Invocation failed"]') is True
    assert is_retryable("Metric logical_consistency failed") is False


def test_result_fetch_retries_empty_and_unscored_rows_to_bound():
    class Cursor:
        description = [("METRIC_NAME",)]

        def __init__(self):
            self.calls = 0

        def execute(self, sql, params=None):
            self.calls += 1

        def fetchall(self):
            return [] if self.calls == 1 else [(None,)] if self.calls == 2 else [("answer_correctness",)]

    plan = type("Plan", (), {"agent_fqn": "DB.S.AGENT"})()
    cursor = Cursor()
    sleeps = []

    assert _fetch_rows(cursor, plan, "run", retries=2, sleep=sleeps.append) == [
        {"metric_name": "answer_correctness"}
    ]
    assert cursor.calls == 3
    assert sleeps == [1, 1]


def _rows():
    return [
        {"record_id": "r1", "input_id": "i1", "ground_truth_ref": "q1", "metric_name": "answer_correctness", "eval_agg_score": 0.8, "test_type": "in_scope"},
        {"record_id": "r2", "input_id": "i2", "ground_truth_ref": "q2", "metric_name": "answer_correctness", "eval_agg_score": 0.4, "test_type": "out_of_scope"},
        {"record_id": "r1", "input_id": "i1", "ground_truth_ref": "q1", "metric_name": "tool_selection_accuracy", "eval_agg_score": 1.0, "test_type": "in_scope"},
        {"record_id": "r2", "input_id": "i2", "ground_truth_ref": "q2", "metric_name": "tool_selection_accuracy", "eval_agg_score": 0.0, "test_type": "out_of_scope"},
    ]


def test_candidate_is_boundary_aware_and_provenance_rich(tmp_path):
    plan = build_plan(
        _config(tmp_path, _manifest()), agent_name="orders_assistant", suite_name="core",
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


def _result(*, score=0.8, passed=True, ids=None):
    plan_identity = {
        "agent_name": "orders_assistant", "suite_name": "core",
        "eval_model": "eval_orders", "agent_fqn": "DB.S.AGENT",
        "dataset_fqn": "DB.EVAL.TABLE", "stage_fqn": "DB.S.STAGE",
    }
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION, "artifact_type": "candidate",
        "agent": "orders_assistant", "suite": "core", "eval_model": "eval_orders",
        "run_name": "run", "timestamp": "20260804_000000",
        "run_metadata": {
            "agent_fqn": "DB.S.AGENT",
            "plan_identity": plan_identity,
            "evaluated_version": "VERSION$1", "git_sha": "abc",
            "pre_start": {"default_version": "VERSION$1", "aliases": {}},
            "post_completion": {"default_version": "VERSION$1", "aliases": {}},
            "default_version_changed": False,
        },
        "plan_schema_version": 1, "suite_signature": "abc123",
        "plan_identity": plan_identity,
        "agent_fqn": "DB.S.AGENT", "dataset_fqn": "DB.EVAL.TABLE", "stage_fqn": "DB.S.STAGE",
        "metric_names": ["answer_correctness"], "status": "completed",
        "summary": {"answer_correctness": {"avg": score, "n": 2}},
        "thresholds": {"answer_correctness": 0.6},
        "regression_tolerances": {"answer_correctness": 0.05},
        "passed": passed, "total_records": 2, "ordered_ground_truth_refs": ids or ["q1", "q2"],
        "results": [{"secret": "detail"}],  # pragma: allowlist secret
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
    threshold = compare_results(build_baseline(_result(score=0.8)), _result(score=0.5, passed=False))
    assert threshold["threshold_failures"]


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


def _legacy_baseline():
    return {
        "agent": "orders_assistant",
        "suite": "core",
        "run_name": "legacy_run",
        "timestamp": "20260731_120000",
        "run_metadata": {"evaluated_version": "VERSION$4", "git_sha": "legacy-sha"},
        "summary": {
            "answer_correctness": {"avg": 0.8, "n": 2},
            "tool_selection_accuracy": {"avg": 1.0, "n": 2},
        },
        "passed": True,
        "total_records": 2,
    }


def test_legacy_baseline_migration_uses_current_plan_and_preserves_provenance(tmp_path):
    plan = build_plan(
        _config(tmp_path, _manifest()),
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(),
    )
    source = tmp_path / "legacy.json"
    source.write_text(json.dumps(_legacy_baseline()))

    baseline, target = migrate_legacy_baseline(source, plan, tmp_path / "new-baselines")

    assert not target.exists()
    assert baseline["schema_version"] == ARTIFACT_SCHEMA_VERSION
    assert baseline["thresholds"] == plan.thresholds
    assert baseline["regression_tolerances"] == plan.regression_tolerances
    assert baseline["ordered_ground_truth_refs"] == plan.ordered_ground_truth_refs
    assert baseline["suite_signature"] == plan.suite_signature
    assert baseline["run_metadata"]["evaluated_version"] == "VERSION$4"
    assert baseline["run_metadata"]["legacy_migration"]["source"] == "legacy.json"
    assert baseline["run_metadata"]["legacy_migration"]["run_metadata"]["git_sha"] == "legacy-sha"

    _, written = migrate_legacy_baseline(
        source, plan, tmp_path / "new-baselines", apply=True
    )
    assert load_result(written, "baseline")["summary"] == baseline["summary"]
    assert migrate_legacy_baseline(source, plan, tmp_path / "new-baselines")[1] == written
    with pytest.raises(FileExistsError):
        migrate_legacy_baseline(source, plan, tmp_path / "new-baselines", apply=True)
    assert migrate_legacy_baseline(
        source, plan, tmp_path / "new-baselines", apply=True, force=True
    )[1] == written

    for legacy_agent in (plan.agent_fqn.rsplit(".", 1)[-1], plan.agent_fqn):
        physical = _legacy_baseline()
        physical["agent"] = legacy_agent
        assert build_migrated_baseline(physical, plan, source)["agent"] == plan.agent_name

    historical_eval = _legacy_baseline()
    historical_eval["agent"] = "ORDERS_ASSISTANT_EVAL"
    with pytest.raises(ValueError, match="_EVAL Agent identity is incompatible"):
        build_migrated_baseline(historical_eval, plan, source)

    near_match = _legacy_baseline()
    near_match["agent"] = f"{plan.agent_fqn.rsplit('.', 1)[-1]}_OTHER"
    with pytest.raises(ValueError, match="agent does not match"):
        build_migrated_baseline(near_match, plan, source)


def test_legacy_baseline_migration_rejects_unknown_shapes_and_policy_drift(tmp_path):
    plan = build_plan(
        _config(tmp_path, _manifest()),
        agent_name="orders_assistant",
        suite_name="core",
        plan_payload=_plan_payload(),
    )
    wrong_metrics = _legacy_baseline()
    wrong_metrics["summary"].pop("tool_selection_accuracy")
    with pytest.raises(ValueError, match="metric set"):
        build_migrated_baseline(wrong_metrics, plan, tmp_path / "legacy.json")

    failed = _legacy_baseline()
    failed["passed"] = False
    with pytest.raises(ValueError, match="accepted passing baseline"):
        build_migrated_baseline(failed, plan, tmp_path / "legacy.json")


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

    assert run_evaluation(config, plan, apply=False, connect=lambda _: pytest.fail("connected")) is None


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
        elif normalized.startswith("SELECT COUNT(*) FROM DB.EVAL.EVAL_ORDERS WHERE OUTPUT:GROUND_TRUTH_OUTPUT"):
            self.rows = [(0,)]
        elif "GROUND_TRUTH_INVOCATIONS" in normalized and normalized.startswith("SELECT COUNT(*)"):
            self.rows = [(0,)]
        elif normalized == "SELECT COUNT(*) FROM DB.EVAL.EVAL_ORDERS":
            self.rows = [(2,)]
        elif normalized.startswith("SELECT INPUT_QUERY, OUTPUT:CUSTOM_CRITERIA:GROUND_TRUTH_REF"):
            self.rows = [("Revenue?", "total_revenue")]
        elif "'START'" in normalized:
            self.starts += 1
        elif "'STATUS'" in normalized:
            self.description = [("RUN_NAME",), ("AGENT",), ("OTHER",), ("STATUS",), ("STATUS_DETAILS",)]
            self.rows = [
                ("run", "agent", None, "FAILED", "Invocation failed")
                if self.starts == 1
                else ("run", "agent", None, "COMPLETED", "")
            ]
        elif "GET_AI_EVALUATION_DATA" in normalized:
            self.description = [
                ("RECORD_ID",), ("INPUT_ID",), ("INPUT",), ("METRIC_NAME",), ("EVAL_AGG_SCORE",)
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


def test_apply_retries_once_and_persists_candidate(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config, agent_name="orders_assistant", suite_name="core",
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
        "USE SCHEMA AGENT_SCHEMA",
    ]
    candidate = load_result(output)
    assert candidate["run_name"] == "candidate_run_r1"
    assert candidate["run_metadata"]["evaluated_version"] == "VERSION$9"
    assert candidate["run_metadata"]["plan_identity"]["agent_fqn"] == plan.agent_fqn
    assert "projection" not in candidate
    assert candidate["ordered_ground_truth_refs"] == ["total_revenue"]
    assert output.parent.name == "core"


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
        _config(tmp_path, _manifest()), agent_name="orders_assistant", suite_name="core",
        plan_payload=_plan_payload(),
    )
    candidate = build_candidate(
        plan=plan, run_name="run", rows=_rows(),
        provenance={
            "agent_fqn": plan.agent_fqn, "evaluated_version": "VERSION$7",
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
        config, agent_name="orders_assistant", suite_name="core",
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
            config, plan, apply=True, allowed_targets=["sandbox"], allowed_databases=["DB"],
            connect=lambda _: connection, sleep=lambda _: None,
        )
    assert not any("CREATE STAGE" in call or "'START'" in call for call in connection.cursor_value.calls)


def test_apply_treats_empty_describe_result_as_missing_agent(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config, agent_name="orders_assistant", suite_name="core",
        plan_payload=_plan_payload(refs=["total_revenue"]),
    )

    class EmptyDescribeCursor(LifecycleCursor):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "DESCRIBE AGENT" in " ".join(sql.split()).upper():
                self.rows = []

    connection = LifecycleConnection()
    connection.cursor_value = EmptyDescribeCursor()
    with pytest.raises(RuntimeError, match="requires existing Agent"):
        run_evaluation(
            config, plan, apply=True, allowed_targets=["sandbox"], allowed_databases=["DB"],
            connect=lambda _: connection, sleep=lambda _: None,
        )
    assert not any("CREATE STAGE" in call or "'START'" in call for call in connection.cursor_value.calls)


def test_apply_fails_when_default_changes_before_start(tmp_path):
    config = _config(tmp_path, _manifest())
    plan = build_plan(
        config, agent_name="orders_assistant", suite_name="core",
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
            config, plan, apply=True, run_name="drift", poll_attempts=1,
            allowed_targets=["sandbox"], allowed_databases=["DB"],
            connect=lambda _: connection, sleep=lambda _: None,
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
            elif normalized.startswith("SELECT INPUT_QUERY, OUTPUT:CUSTOM_CRITERIA:GROUND_TRUTH_REF"):
                self.rows = self.identity_rows

        def fetchall(self): return self.rows
        def fetchone(self): return self.rows[0]

    with pytest.raises(ValueError, match="duplicate ground_truth_ref"):
        validate_table(
            Cursor([("one", "q1"), ("two", "q1")]), "DB.S.T",
            ["logical_consistency"], ["q1", "q2"],
        )
    with pytest.raises(ValueError, match="duplicate INPUT_QUERY"):
        validate_table(
            Cursor([("same", "q1"), ("same", "q2")]), "DB.S.T",
            ["logical_consistency"], ["q1", "q2"],
        )