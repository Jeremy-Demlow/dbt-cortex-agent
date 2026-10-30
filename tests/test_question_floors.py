from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_eval import LifecycleCursor, _config, _manifest, _plan_payload

from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.eval.baseline import build_baseline
from dbt_cortex_agent.eval.compare import compare_results
from dbt_cortex_agent.eval.dataset import SYSTEM_METRICS
from dbt_cortex_agent.eval.gate import gate_candidate
from dbt_cortex_agent.eval.lifecycle import (
    _plan_from_payload,
    run_evaluation,
    validate_evaluation_apply,
)
from dbt_cortex_agent.eval.question_policy import (
    validate_question_policy,
    validate_question_snapshot,
)
from dbt_cortex_agent.eval.results import (
    build_candidate,
    compute_summary,
    eligibility_failures,
    validate_result,
    write_candidate,
)
from dbt_cortex_agent.eval.verify import VerifySelection, _bind_candidate, verify_evaluations

ROOT = Path(__file__).parents[1]


def _meta(floor=0.8):
    return {
        "metrics": ["answer_correctness", "tool_selection_accuracy"],
        "questions": [
            {
                "id": "critical",
                "ground_truth_ref": "q1",
                "thresholds": {"answer_correctness": floor},
            },
            {"id": "ordinary", "ground_truth_ref": "q2"},
        ],
    }


def _policy(macro_harness, meta=None):
    return macro_harness.call("cortex_eval__question_policy", meta or _meta())


def _plan(macro_harness, floor=0.8):
    payload = _plan_payload()
    payload["schema_version"] = 3
    payload["question_policy"] = _policy(macro_harness, _meta(floor))
    signed = json.loads(payload["signature_material"])
    signed.update(plan_schema_version=3, question_policy=payload["question_policy"])
    payload["signature_material"] = json.dumps(signed)
    payload["suite_signature"] = hashlib.md5(payload["signature_material"].encode()).hexdigest()
    return _plan_from_payload(payload, "orders_assistant", "core")


def _candidate(plan, critical=0.8):
    rows = [
        {
            "ground_truth_ref": reference,
            "metric_name": name,
            "test_type": plan.question_policy.get("test_types", {}).get(reference, "in_scope"),
            "eval_agg_score": (
                critical if reference == "q1" and name == "answer_correctness" else 1.0
            )
            if name in SYSTEM_METRICS
            else 5,
        }
        for reference in plan.ordered_ground_truth_refs
        for name in plan.metric_names
    ]
    return build_candidate(
        plan=plan,
        run_name="run",
        rows=rows,
        provenance={
            "plan_identity": plan.plan_identity,
            "pre_start": {"default_version": "VERSION$1"},
            "post_completion": {"default_version": "VERSION$1"},
            "evaluated_version": "VERSION$1",
            "default_version_changed": False,
        },
    )


def test_green_average_cannot_hide_failed_question(macro_harness, tmp_path):
    plan = _plan(macro_harness)
    candidate = _candidate(plan, critical=0.4)
    assert candidate["summary"]["answer_correctness"]["avg"] == 0.7
    assert candidate["passed"] is False
    assert candidate["threshold_failures"] == ["question q1/answer_correctness: 0.400 < 0.800"]
    baseline = build_baseline(_candidate(plan))
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline))
    # An edited flag or cleared failure list is never authority for a pass.
    candidate.update(passed=True, threshold_failures=[])
    assert eligibility_failures(candidate)
    assert compare_results(baseline, candidate)["passed"] is False
    candidate_path = write_candidate(candidate, tmp_path)
    assert gate_candidate(candidate_path, baseline=baseline_path)["passed"] is False
    with pytest.raises(ValueError, match="cannot become baselines"):
        build_baseline(candidate)


@pytest.mark.parametrize("value", [True, None, "0.8", float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_floor_rejected_by_dbt_and_python(macro_harness, value):
    with pytest.raises(ValueError):
        _policy(macro_harness, _meta(value))
    policy = _policy(macro_harness)
    policy["thresholds"]["q1"]["answer_correctness"] = value
    with pytest.raises(ValueError):
        validate_question_policy(policy, ["q1", "q2"], _meta()["metrics"])


@pytest.mark.parametrize("damage", ["unknown_metric", "bad_map", "ref", "tool", "ranges"])
def test_invalid_metadata_rejected(macro_harness, damage):
    meta = _meta()
    question = meta["questions"][0]
    if damage == "unknown_metric":
        question["thresholds"] = {"missing": 0.5}
    elif damage == "bad_map":
        question["thresholds"] = None
    elif damage == "ref":
        question["ground_truth_ref"] = " "
    elif damage == "tool":
        question.update(test_type="negative", thresholds={"tool_selection_accuracy": 0.8})
    else:
        meta["metrics"].append({"name": "custom", "prompt": "Score"})
        question["thresholds"] = {"custom": 4}
    with pytest.raises(ValueError):
        _policy(macro_harness, meta)


def test_custom_ranges_and_boundary_answer_floor(macro_harness):
    meta = _meta()
    meta["metrics"].append(
        {
            "name": "custom",
            "prompt": "Score",
            "score_ranges": {"min_score": [1, 2], "median_score": [3, 3], "max_score": [4, 5]},
        }
    )
    meta["questions"][0].update(test_type="negative", thresholds={"custom": 4})
    policy = _policy(macro_harness, meta)
    assert policy["score_bounds"] == {"custom": [1, 5]}
    validate_question_policy(policy, ["q1", "q2"], ["custom"], meta["metrics"])
    meta["metrics"][-1]["score_ranges"]["median_score"] = [4, 3]
    with pytest.raises(ValueError, match="ordered"):
        _policy(macro_harness, meta)


@pytest.mark.parametrize("damage", ["missing", "duplicate", "nan", "range", "type", "summary"])
def test_malformed_evidence_never_passes(macro_harness, damage):
    candidate = _candidate(_plan(macro_harness))
    if damage == "missing":
        candidate["results"].pop(0)
    elif damage == "duplicate":
        candidate["results"].append(dict(candidate["results"][0]))
    elif damage == "summary":
        candidate["summary"]["answer_correctness"]["avg"] = 1
    else:
        candidate["results"][0].update(
            {
                "nan": {"eval_agg_score": float("nan")},
                "range": {"eval_agg_score": 1.1},
                "type": {"test_type": "negative"},
            }[damage]
        )
        if damage == "range":
            candidate["summary"] = compute_summary(candidate["results"])
    with pytest.raises(ValueError):
        validate_result(candidate)


def test_baseline_retains_rows_and_replays_floors(macro_harness):
    baseline = build_baseline(_candidate(_plan(macro_harness)))
    assert baseline["schema_version"] == baseline["plan_schema_version"] == 3
    assert baseline["results"]
    baseline["results"][0]["eval_agg_score"] = 0.4
    baseline["summary"] = compute_summary(baseline["results"])
    assert eligibility_failures(baseline)
    baseline.pop("results")
    with pytest.raises(ValueError, match="row evidence"):
        validate_result(baseline)


@pytest.mark.parametrize("floor", [0.7, 0.9])
def test_changed_policy_incomparable_and_verify_bound(macro_harness, floor):
    plan = _plan(macro_harness)
    other = _plan(macro_harness, floor)
    assert plan.suite_signature != other.suite_signature
    candidate = _candidate(other, critical=1)
    result = compare_results(build_baseline(_candidate(plan)), candidate)
    assert result["suite_change"] == "question threshold policy changed"
    assert result["passed"] is False
    # Even a copied signature cannot bypass the explicit policy comparison/binding.
    candidate["suite_signature"] = plan.suite_signature
    with pytest.raises(ValueError, match="question_policy"):
        _bind_candidate(candidate, plan)


def test_opt_in_versions_and_legacy_behavior(macro_harness):
    legacy = _plan_from_payload(_plan_payload(), "orders_assistant", "core")
    candidate = _candidate(legacy, critical=0.4)
    assert candidate["passed"] is True
    assert candidate["schema_version"] == 2 and "question_policy" not in candidate
    assert "results" not in build_baseline(candidate)
    comparison = compare_results(build_baseline(candidate), _candidate(_plan(macro_harness)))
    assert not comparison["passed"]
    opted = _candidate(_plan(macro_harness))
    for field in ("schema_version", "plan_schema_version"):
        bad = copy.deepcopy(opted)
        bad[field] = 2
        with pytest.raises(ValueError, match="schema_version"):
            validate_result(bad)
    opted.pop("question_policy")
    with pytest.raises(ValueError, match="schema_version"):
        validate_result(opted)


def test_real_dbt_plan_render_signs_only_nonempty_policy(macro_harness):
    meta = _meta()
    meta.update(agent="orders_assistant", name="core")
    node = SimpleNamespace(name="eval_orders", database="DB", schema="EVAL")
    macro_harness.override("cortex_eval__get_suite", lambda *_: node)
    macro_harness.override("cortex_eval__validate", lambda *_: True)
    macro_harness.override("cortex_eval__get_eval_meta", lambda *_: meta)
    macro_harness.override("cortex_agent__get_agent", lambda *_: node)
    macro_harness.override("cortex_agent__agent_meta", lambda *_: {})
    macro_harness.override("cortex_agent__resource_agent_fqn", lambda *_: "DB.S.AGENT")
    macro_harness.override("cortex_eval__dataset_fqn", lambda *_: "DB.EVAL.DATA")
    macro_harness.override("cortex_eval__default_stage_fqn", lambda *_: "DB.S.STAGE")
    macro_harness.context.update(
        target=SimpleNamespace(
            name="sandbox", role="ROLE", database="DB", schema="S", warehouse="WH"
        ),
        local_md5=lambda text: hashlib.md5(text.encode()).hexdigest(),
    )

    def render():
        return json.loads(
            macro_harness.call("cortex_eval__execution_plan", "orders_assistant", "core")
        )

    opted = render()
    plan = _plan_from_payload(opted, "orders_assistant", "core")
    assert plan.schema_version == 3 and plan.question_policy == _policy(macro_harness)
    opted["question_policy"]["thresholds"]["q1"]["answer_correctness"] = 0.1
    with pytest.raises(ValueError, match="signed fields"):
        _plan_from_payload(opted, "orders_assistant", "core")
    meta["questions"][0].pop("thresholds")
    absent = render()
    meta["questions"][0]["thresholds"] = {}
    empty = render()
    assert absent == empty
    assert absent["schema_version"] == 2 and "question_policy" not in absent


@pytest.mark.parametrize("macro", ["cortex_eval__gate", "cortex_eval__run"])
def test_native_policy_guard_before_effects(macro_harness, macro):
    macro_harness.override("cortex_eval__get_eval_meta", lambda *_: _meta())
    macro_harness.context.update(invocation_id="abc", run_query=lambda *_: pytest.fail("query"))
    macro_harness.override("cortex_eval__default_stage_fqn", lambda: "DB.S.STAGE")
    args = {"results_fqn": "DB.S.RESULTS"} if macro.endswith("gate") else {"dry_run": False}
    with pytest.raises(ValueError, match="unsupported.*native macro"):
        macro_harness.call(macro, "eval_orders", **args)


def test_source_type_disagreement_stops_before_start(macro_harness, tmp_path):
    plan = _plan(macro_harness)
    plan = replace(
        plan,
        ordered_ground_truth_refs=["total_revenue"],
        question_policy={
            **plan.question_policy,
            "thresholds": {"total_revenue": {"tool_selection_accuracy": 0.8}},
            "score_bounds": {"tool_selection_accuracy": [0, 1]},
            "test_types": {"total_revenue": "in_scope"},
        },
    )
    with pytest.raises(ValueError, match="differs from dataset"):
        validate_question_snapshot(
            plan.question_policy, (("Revenue?", "negative", "total_revenue"),)
        )

    class Cursor(LifecycleCursor):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if sql.startswith("SELECT input_query"):
                self.rows = [("Revenue?", "negative", "total_revenue")]

    cursor = Cursor()
    connection = SimpleNamespace(cursor=lambda: cursor, close=lambda: None)
    cursor.close = lambda: None
    with pytest.raises(ValueError, match="differs from dataset"):
        run_evaluation(
            _config(tmp_path, _manifest()),
            plan,
            apply=True,
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            connect=lambda _: connection,
        )
    assert cursor.starts == 0
    assert not any("COPY INTO" in call for call in cursor.calls)


@pytest.mark.parametrize("baseline_present", [True, False])
def test_verify_fails_question_with_or_without_baseline(macro_harness, tmp_path, baseline_present):
    plan = _plan(macro_harness)
    candidate = _candidate(plan, critical=0.4)
    candidate.update(passed=True, threshold_failures=[])
    candidate_path = write_candidate(candidate, tmp_path)
    baseline_path = tmp_path / "baseline.json"
    if baseline_present:
        baseline_path.write_text(json.dumps(build_baseline(_candidate(plan))))
    result = verify_evaluations(
        _config(tmp_path / "consumer", _manifest()),
        (VerifySelection(plan, baseline_path),),
        apply=True,
        allowed_targets=["sandbox"],
        allowed_databases=["DB"],
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
        runner=CommandRunner(lambda command, **_: subprocess.CompletedProcess(command, 0, "", "")),
        render_plan=lambda *_, **__: plan,
        evaluate=lambda *_, **__: candidate_path,
    )
    assert result["passed"] is False and result["outcome"] == "quality_failed"


def test_question_policy_docs_are_explicit():
    text = (ROOT / "docs/guides/evaluations.md").read_text()
    for phrase in ("questions[].thresholds", "schema v3", "native macro", "ground_truth_ref"):
        assert phrase in text
    for phrase in (
        "preview.executable: false",
        "preview_unresolved",
        "preview.dataset_exists: null",
        "Do not upload preview output",
        "not live dbt qualification",
    ):
        assert phrase in text
    reference = (ROOT / "docs/reference/macros.md").read_text()
    for phrase in ("dry_run=false", "execute_checks=false", "not executable START configs"):
        assert phrase in reference


@pytest.mark.parametrize("test_type", ["negative", "out_of_scope"])
def test_tool_floor_cannot_be_excluded_by_declared_boundary(macro_harness, test_type):
    meta = _meta()
    meta["questions"][0].update(test_type=test_type, thresholds={"tool_selection_accuracy": 0.5})
    with pytest.raises(ValueError, match="in_scope"):
        _policy(macro_harness, meta)
    policy = _policy(macro_harness)
    policy["thresholds"]["q1"] = {"tool_selection_accuracy": 0.5}
    policy["score_bounds"] = {"tool_selection_accuracy": [0, 1]}
    policy["test_types"]["q1"] = test_type
    with pytest.raises(ValueError, match="in_scope"):
        validate_question_policy(policy, ["q1", "q2"], _meta()["metrics"])


@pytest.mark.parametrize("damage", ["ref", "metric", "bounds", "types", "empty"])
def test_signed_invalid_policy_rejected_before_connection(macro_harness, tmp_path, damage):
    plan = _plan(macro_harness)
    policy = copy.deepcopy(plan.question_policy)
    if damage == "ref":
        policy["thresholds"]["unknown"] = policy["thresholds"].pop("q1")
        policy["test_types"]["unknown"] = policy["test_types"].pop("q1")
    elif damage == "metric":
        policy["thresholds"]["q1"] = {"unknown": 0.8}
    elif damage == "bounds":
        policy["score_bounds"]["answer_correctness"] = [0, 2]
    elif damage == "types":
        policy["test_types"] = {}
    else:
        policy["thresholds"] = {}
    with pytest.raises(ValueError):
        validate_evaluation_apply(
            _config(tmp_path, _manifest()),
            [replace(plan, question_policy=policy)],
            allowed_targets=["sandbox"],
            allowed_databases=["DB"],
            poll_attempts=1,
            poll_interval=0,
            transient_retries=0,
        )


def test_custom_and_tool_floors_replay_with_boundary_exclusions(macro_harness):
    meta = _meta()
    custom = {
        "name": "quality",
        "prompt": "Score",
        "score_ranges": {"min_score": [1, 2], "median_score": [3, 3], "max_score": [4, 5]},
    }
    meta["metrics"].append(custom)
    meta["questions"][0]["thresholds"] = {"tool_selection_accuracy": 1.0}
    meta["questions"][1].update(test_type="negative", thresholds={"quality": 4})
    plan = replace(
        _plan(macro_harness),
        metric_names=[*_meta()["metrics"], "quality"],
        native_eval_config={"metrics": meta["metrics"]},
        question_policy=_policy(macro_harness, meta),
    )
    candidate = _candidate(plan)
    for row in candidate["results"]:
        row["test_type"] = "negative" if row["ground_truth_ref"] == "q2" else "in_scope"
        if row["metric_name"] == "quality":
            row["eval_agg_score"] = 5 if row["ground_truth_ref"] == "q1" else 4
    candidate["summary"] = compute_summary(candidate["results"])
    assert not eligibility_failures(candidate)
    validate_result(build_baseline(candidate))
    tool = next(
        row
        for row in candidate["results"]
        if (row["ground_truth_ref"] == "q1" and row["metric_name"] == "tool_selection_accuracy")
    )
    tool["eval_agg_score"] = 0.9
    candidate["summary"] = compute_summary(candidate["results"])
    assert any(
        "question q1/tool_selection_accuracy" in item for item in eligibility_failures(candidate)
    )


def test_eval_run_rechecks_question_eligibility(macro_harness, tmp_path, monkeypatch, capsys):
    from dbt_cortex_agent.commands import eval as commands

    plan = _plan(macro_harness)
    candidate = _candidate(plan, critical=0.4)
    candidate.update(passed=True, threshold_failures=[])
    monkeypatch.setattr(commands, "build_plan", lambda *_, **__: plan)
    monkeypatch.setattr(commands, "run_evaluation", lambda *_, **__: tmp_path / "candidate.json")
    monkeypatch.setattr(commands, "load_result", lambda _: candidate)
    args = SimpleNamespace(
        agent="orders_assistant",
        suite="core",
        apply=False,
        no_parse=False,
        agent_version=None,
        run_name=None,
        poll_attempts=1,
        poll_interval=0,
        transient_retries=0,
        allow_target=[],
        allow_database=[],
        json=True,
    )
    assert commands._handle_run(args, _config(tmp_path, _manifest())) == 1
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["passed"] is False
    assert emitted["plan"]["question_policy"] == plan.question_policy


def test_real_eval_validation_checks_duplicate_refs_and_policy(macro_harness):
    meta = _meta()
    meta.update(agent="orders_assistant", name="core")
    node = SimpleNamespace(config={"materialized": "table"})
    macro_harness.override("cortex_eval__get_eval", lambda *_: node)
    macro_harness.override("cortex_eval__get_eval_meta", lambda *_: meta)
    macro_harness.override("cortex_agent__get_agent", lambda *_: {})
    macro_harness.override("cortex_agent__agent_meta", lambda *_: {})
    macro_harness.override("cortex_eval__native_supported_tool_names", lambda *_: [])
    macro_harness.override("cortex_eval__unsupported_native_tool_claims", lambda *_: {})
    macro_harness.override("cortex_eval__dataset_fqn", lambda *_: "DB.EVAL.DATA")
    assert macro_harness.call("cortex_eval__validate", "eval_orders", False)
    meta["questions"][1]["ground_truth_ref"] = "q1"
    with pytest.raises(ValueError, match="duplicate ground_truth_ref"):
        macro_harness.call("cortex_eval__validate", "eval_orders", False)
    meta["questions"][1]["ground_truth_ref"] = "q2"
    meta["questions"][0]["thresholds"] = {"answer_correctness": float("nan")}
    with pytest.raises(ValueError, match="finite"):
        macro_harness.call("cortex_eval__validate", "eval_orders", False)


def test_policy_rekeying_incomparable_even_with_same_signature(macro_harness):
    candidate = _candidate(_plan(macro_harness), critical=1)
    baseline = build_baseline(candidate)
    candidate = copy.deepcopy(candidate)
    candidate["question_policy"]["thresholds"]["q2"] = candidate["question_policy"][
        "thresholds"
    ].pop("q1")
    candidate["question_policy"]["test_types"]["q2"] = candidate["question_policy"][
        "test_types"
    ].pop("q1")
    comparison = compare_results(baseline, candidate)
    assert comparison["suite_change"] == "question threshold policy changed"
    assert comparison["passed"] is False


def test_question_baseline_preview_cannot_claim_failed_acceptance(
    macro_harness, tmp_path, monkeypatch
):
    from dbt_cortex_agent.commands import eval as commands

    candidate = _candidate(_plan(macro_harness), critical=0.4)
    candidate.update(passed=True, threshold_failures=[])
    monkeypatch.setattr(commands, "load_result", lambda _: candidate)
    args = SimpleNamespace(
        candidate="candidate.json", baseline_dir=None, force=False, apply=False, json=True
    )
    with pytest.raises(ValueError, match="cannot become baselines"):
        commands._handle_accept(args, _config(tmp_path, _manifest()))


@pytest.fixture
def native_preview_context(macro_harness):
    meta = _meta()
    meta.update(agent="orders_assistant", name="core")
    eval_config = {"materialized": "table", "meta": {"cortex_eval": meta}}
    eval_node = SimpleNamespace(
        name="eval_orders",
        alias="DATA",
        resource_type="model",
        database="DB",
        schema="EVAL",
        config=SimpleNamespace(meta=eval_config["meta"], get=eval_config.get),
    )
    agent_node = SimpleNamespace(
        name="orders_assistant",
        alias="AGENT",
        resource_type="model",
        database="DB",
        schema="AGENTS",
        config={"materialized": "cortex_agent", "meta": {"cortex_agent": {}}},
    )
    queries, logs = [], []

    def forbidden_query(sql):
        queries.append(sql)
        pytest.fail(f"Native preview attempted a query: {sql}")

    macro_harness.context.update(
        graph=SimpleNamespace(nodes={"eval": eval_node, "agent": agent_node}),
        target=SimpleNamespace(
            database="DB", schema="PUBLIC", name="sandbox", role="ROLE", warehouse="WH"
        ),
        invocation_id="abc-123",
        var=lambda _name, default=None: default,
        run_query=forbidden_query,
        log=lambda message, **_: logs.append(message),
        local_md5=lambda value: hashlib.md5(value.encode()).hexdigest(),
    )
    return meta, queries, logs


@pytest.mark.parametrize("with_policy", [False, True])
@pytest.mark.parametrize("execute_checks", [False, True])
@pytest.mark.parametrize("entry", ["run", "start", "render_config", "build_config"])
def test_native_policy_dry_run_remains_offline(
    macro_harness, native_preview_context, entry, execute_checks, with_policy
):
    meta, queries, logs = native_preview_context
    if not with_policy:
        meta["questions"][0].pop("thresholds")
    kwargs = {"dry_run": True}
    if entry != "run":
        kwargs["execute_checks"] = execute_checks
    result = macro_harness.call(f"cortex_eval__{entry}", "eval_orders", **kwargs)
    assert macro_harness.context["execute"] is True
    assert queries == []
    if entry == "build_config":
        config = result
    elif entry == "render_config":
        config = json.loads(result)
    else:
        assert result == "orders_assistant_core_eval_abc123"
        config = next(json.loads(message) for message in logs if message.startswith("{"))
    assert config["preview"] == {
        "executable": False,
        "dataset_content_hash": "preview_unresolved",
        "dataset_exists": None,
        "include_dataset": None,
    }
    assert config["evaluation"]["source_metadata"]["dataset_name"] == (
        "DB.EVAL.ORDERS_ASSISTANT_CORE_DS_preview_unresolved"
    )
    assert "dataset" not in config
    assert any("not executable" in message for message in logs)
    assert not any("would create dataset" in message for message in logs)
    assert not any("would reuse existing dataset" in message for message in logs)


@pytest.mark.parametrize("include_dataset", [None, False, True])
def test_native_preview_explicit_dataset_shape_is_not_existence_proof(
    macro_harness, native_preview_context, include_dataset
):
    _, queries, _ = native_preview_context
    config = macro_harness.call(
        "cortex_eval__build_config",
        "eval_orders",
        dataset_name="DB.EVAL.NAMED",
        execute_checks=True,
        include_dataset=include_dataset,
        dry_run=True,
    )
    assert queries == []
    assert config["preview"]["dataset_exists"] is None
    assert config["preview"]["include_dataset"] is include_dataset
    assert ("dataset" in config) is (include_dataset is True)
    assert config["evaluation"]["source_metadata"]["dataset_name"] == (
        "DB.EVAL.NAMED_DS_preview_unresolved"
    )


@pytest.mark.parametrize("dataset_name", [None, "DB.EVAL.NAMED"])
@pytest.mark.parametrize("dataset_exists", [False, True])
def test_normal_native_renderer_retains_content_hash_and_inventory_queries(
    macro_harness, native_preview_context, dataset_name, dataset_exists
):
    _, queries, _ = native_preview_context
    prefix = dataset_name or "DB.EVAL.ORDERS_ASSISTANT_CORE"
    expected_name = prefix + "_DS_987654"

    class Inventory(list):
        column_names = ["name"]

    def query(sql):
        queries.append(sql)
        if "HASH_AGG" in sql:
            assert "FROM DB.EVAL.DATA" in sql
            return SimpleNamespace(rows=[("987654",)])
        assert sql == "SHOW DATASETS IN SCHEMA DB.EVAL"
        return Inventory([(expected_name.split(".")[-1],)] if dataset_exists else [])

    macro_harness.context["run_query"] = query
    # Existing positional arguments and the default renderer behavior are unchanged.
    config = json.loads(
        macro_harness.call(
            "cortex_eval__render_config", "eval_orders", "review", dataset_name, False
        )
    )
    assert len(queries) == 2
    assert "preview" not in config
    assert config["evaluation"]["source_metadata"]["dataset_name"] == expected_name
    assert ("dataset" in config) is (not dataset_exists)
    assert config == macro_harness.call(
        "cortex_eval__native_config",
        native_preview_context[0],
        "DB.AGENTS.AGENT",
        "DB.EVAL.DATA",
        expected_name,
        "review",
        not dataset_exists,
    )


@pytest.mark.parametrize("with_policy", [False, True])
def test_native_preview_does_not_change_signed_execution_plan(
    macro_harness, native_preview_context, with_policy
):
    meta, queries, _ = native_preview_context
    if not with_policy:
        meta["questions"][0].pop("thresholds")
    before = macro_harness.call("cortex_eval__execution_plan", "orders_assistant", "core")
    macro_harness.call("cortex_eval__run", "eval_orders", dry_run=True)
    after = macro_harness.call("cortex_eval__execution_plan", "orders_assistant", "core")
    assert before == after
    payload = json.loads(after)
    assert payload["schema_version"] == (3 if with_policy else 2)
    assert "preview_unresolved" not in after
    assert "preview" not in payload["native_eval_config"]
    assert payload["dataset_name_token"] == "__DBT_CORTEX_AGENT_DATASET_NAME__"
    assert queries == []


def test_native_preview_still_validates_metadata(macro_harness, native_preview_context):
    meta, queries, _ = native_preview_context
    meta["questions"][0]["thresholds"] = {"undeclared": 0.8}
    with pytest.raises(ValueError, match="undeclared"):
        macro_harness.call("cortex_eval__run", "eval_orders", dry_run=True)
    assert queries == []


@pytest.mark.parametrize("entry", ["render_config", "build_config"])
def test_parse_context_never_invents_dataset_identity(macro_harness, native_preview_context, entry):
    _, queries, _ = native_preview_context
    macro_harness.context["execute"] = False
    result = macro_harness.call(f"cortex_eval__{entry}", "eval_orders", execute_checks=True)
    config = json.loads(result) if entry == "render_config" else result
    assert config["preview"]["executable"] is False
    assert config["preview"]["dataset_exists"] is None
    assert "preview_unresolved" in config["evaluation"]["source_metadata"]["dataset_name"]
    assert "abc123" not in config["evaluation"]["source_metadata"]["dataset_name"]
    assert queries == []


@pytest.mark.parametrize("entry", ["run", "start"])
def test_native_preview_rejects_unsafe_run_name_before_queries(
    macro_harness, native_preview_context, entry
):
    _, queries, _ = native_preview_context
    with pytest.raises(ValueError, match="letters, digits, and underscores"):
        macro_harness.call(
            f"cortex_eval__{entry}", "eval_orders", run_name="unsafe-name", dry_run=True
        )
    assert queries == []


def test_normal_native_start_renders_real_hash_and_keeps_live_checks(
    macro_harness, native_preview_context
):
    _, queries, _ = native_preview_context
    config_uploads = []

    class Table(list):
        @property
        def rows(self):
            return self

        column_names = ["name"]

    def query(sql):
        queries.append(sql)
        if sql.startswith("DESCRIBE TABLE"):
            assert sql == "DESCRIBE TABLE DB.EVAL.DATA"
            return Table([("INPUT_QUERY",), ("OUTPUT",)])
        if sql.startswith("SELECT COUNT(*)"):
            return Table([(0 if " IS NULL" in sql else 1,)])
        if "HASH_AGG" in sql:
            return Table([("987654",)])
        if sql.startswith("SHOW DATASETS"):
            return Table([])
        if sql.startswith("COPY INTO"):
            config_uploads.append(json.loads(sql.split("$$")[1]))
        else:
            assert sql.startswith(("CREATE STAGE IF NOT EXISTS", "CALL EXECUTE_AI_EVALUATION"))
        return Table([])

    variables = {
        "cortex_agent_allowed_targets": ["sandbox"],
        "cortex_agent_allowed_databases": ["DB"],
    }
    macro_harness.context.update(
        run_query=query, var=lambda name, default=None: variables.get(name, default)
    )
    assert (
        macro_harness.call(
            "cortex_eval__start", "eval_orders", "approved_run", None, None, False, True
        )
        == "approved_run"
    )
    assert queries[0] == "DESCRIBE TABLE DB.EVAL.DATA"
    assert any("ground_truth_output IS NULL" in sql for sql in queries)
    assert any("ground_truth_invocations IS NULL" in sql for sql in queries)
    assert any("HASH_AGG" in sql for sql in queries)
    assert queries[-4] == "SHOW DATASETS IN SCHEMA DB.EVAL"
    assert queries[-1].startswith("CALL EXECUTE_AI_EVALUATION('START'")
    assert len(config_uploads) == 1
    assert "preview" not in config_uploads[0]
    assert config_uploads[0]["dataset"]["dataset_name"].endswith("_DS_987654")


def test_native_preview_is_not_an_accepted_execution_plan(macro_harness, native_preview_context):
    config = json.loads(
        macro_harness.call("cortex_eval__render_config", "eval_orders", dry_run=True)
    )
    with pytest.raises(ValueError, match="schema_version"):
        _plan_from_payload(config, "orders_assistant", "core")
