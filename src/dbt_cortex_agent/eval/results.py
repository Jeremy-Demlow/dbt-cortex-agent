from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..artifacts import ARTIFACT_SCHEMA_VERSION, artifact_slug, contained_path
from ..domain import finite_number
from .dataset import TOOL_METRICS, annotate_rows, validate_metric_policy, validate_snapshot

CURRENT_PLAN_SCHEMA_VERSION = 2


def _identity_components(value: dict[str, Any]) -> tuple[str, str, str, str]:
    identity = value.get("plan_identity") or {}
    target = artifact_slug(str(identity.get("target_name") or "unknown"), "target")
    parts = str(value.get("agent_fqn") or "").split(".")
    if len(parts) != 3:
        raise ValueError("Evaluation artifact agent_fqn must have database.schema.object")
    database, schema, name = (artifact_slug(part, "Agent FQN component") for part in parts)
    return (target, database, schema, name)


def compute_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        name = row.get("metric_name")
        score = row.get("eval_agg_score")
        if not name or score is None:
            continue
        if name in TOOL_METRICS and row.get("test_type", "in_scope") != "in_scope":
            continue
        grouped.setdefault(str(name), []).append(finite_number(score, f"score for {name}"))
    return {
        name: {
            "avg": finite_number(sum(scores) / len(scores), f"average for {name}"),
            "n": len(scores),
        }
        for name, scores in sorted(grouped.items())
    }


def _observation_identity(row: Any, refs: set[str], metrics: set[str]) -> tuple[str, str, str]:
    if not isinstance(row, dict):
        raise ValueError("Evaluation observation must be an object")
    reference, metric = row.get("ground_truth_ref"), row.get("metric_name")
    if not isinstance(reference, str) or reference not in refs:
        raise ValueError("Evaluation observation has missing or undeclared ground-truth ref")
    if not isinstance(metric, str) or metric not in metrics:
        raise ValueError("Evaluation observation has missing or undeclared metric")
    test_type = row.get("test_type", "in_scope")
    if not isinstance(test_type, str) or not test_type.strip():
        raise ValueError("Evaluation observation test_type must be a nonblank string")
    return reference, metric, test_type


def validate_observations(rows: list[dict[str, Any]], refs: list[str], metrics: list[str]) -> None:
    if not isinstance(rows, list) or not rows:
        raise ValueError("Evaluation requires scored row evidence")
    expected_refs, expected_metrics = set(refs), set(metrics)
    observed: dict[str, set[str]] = {}
    test_types: dict[str, str] = {}
    for row in rows:
        reference, metric, test_type = _observation_identity(row, expected_refs, expected_metrics)
        if reference in test_types and test_types[reference] != test_type:
            raise ValueError("Evaluation observations have inconsistent test_type for a ref")
        test_types[reference] = test_type
        seen = observed.setdefault(reference, set())
        if metric in seen:
            raise ValueError("Evaluation has duplicate ground-truth ref/metric observations")
        seen.add(metric)
        if metric not in TOOL_METRICS or test_type == "in_scope":
            finite_number(row.get("eval_agg_score"), f"score for {metric}")
    if set(observed) != expected_refs:
        raise ValueError("Evaluation observations do not cover the declared ground-truth refs")
    for reference, seen in observed.items():
        required = expected_metrics - (
            TOOL_METRICS if test_types[reference] != "in_scope" else set()
        )
        if not required <= seen:
            raise ValueError("Evaluation observations are missing required metrics")


def eligibility_failures(value: dict[str, Any]) -> list[str]:
    failures = []
    if value.get("status") != "completed":
        failures.append("Evaluation status must be completed")
    if value.get("passed") is not True:
        failures.append("Evaluation passed must be exactly true")
    if value.get("threshold_failures"):
        failures.append("Evaluation records intrinsic failures")
    failures.extend(threshold_failures(value["summary"], value["thresholds"]))
    for metric in value["regression_tolerances"]:
        if metric not in value["summary"]:
            failures.append(f"{metric}: missing regression metric")
    return failures


def threshold_failures(
    summary: dict[str, dict[str, Any]], thresholds: dict[str, float]
) -> list[str]:
    failures: list[str] = []
    for metric, threshold in thresholds.items():
        stats = summary.get(metric)
        if not stats or stats.get("avg") is None:
            failures.append(f"{metric}: missing threshold metric")
        elif finite_number(stats["avg"], f"average for {metric}") < finite_number(
            threshold, f"threshold for {metric}"
        ):
            failures.append(f"{metric}: {float(stats['avg']):.3f} < {float(threshold):.3f}")
    return failures


def build_candidate(
    *, plan, run_name: str, rows: list[dict[str, Any]], provenance: dict[str, Any]
) -> dict[str, Any]:
    validate_metric_policy(plan.metric_names, plan.thresholds, plan.regression_tolerances)
    validate_observations(rows, plan.ordered_ground_truth_refs, plan.metric_names)
    summary = compute_summary(rows)
    failures = threshold_failures(summary, plan.thresholds)
    failures.extend(
        f"{metric}: missing regression metric"
        for metric in plan.regression_tolerances
        if metric not in summary
    )
    drift = provenance.get("default_version_changed") is True
    if drift:
        failures.append("Agent DEFAULT version changed during evaluation; result is indeterminate")
    source_drift = provenance.get("dataset_source_changed") is True
    if source_drift:
        failures.append("Evaluation dataset source changed; result is indeterminate")
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "candidate",
        "agent": plan.agent_name,
        "suite": plan.suite_name,
        "eval_model": plan.eval_model,
        "run_name": run_name,
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "run_metadata": provenance,
        "plan_schema_version": plan.schema_version,
        "suite_signature": plan.suite_signature,
        "plan_identity": plan.plan_identity,
        "agent_fqn": plan.agent_fqn,
        "dataset_fqn": plan.table_fqn,
        "stage_fqn": plan.stage_fqn,
        "metric_names": plan.metric_names,
        "summary": summary,
        "thresholds": plan.thresholds,
        "regression_tolerances": plan.regression_tolerances,
        "passed": not failures,
        "status": "indeterminate" if drift or source_drift else "completed",
        "threshold_failures": failures,
        "total_records": len({row["ground_truth_ref"] for row in rows}),
        "ordered_ground_truth_refs": plan.ordered_ground_truth_refs,
        "results": rows,
    }


def write_candidate(candidate: dict[str, Any], artifact_dir: str | Path) -> Path:
    validate_result(candidate, "candidate")
    target_name, database, schema, agent_object = _identity_components(candidate)
    target = contained_path(
        artifact_dir,
        "candidates",
        target_name,
        database,
        schema,
        agent_object,
        candidate["suite"],
        f"{candidate['run_name']}.json",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Evaluation candidate already exists: {target}")
    target.write_text(json.dumps(candidate, indent=2, default=str) + "\n", encoding="utf-8")
    return target


def write_diagnostic(diagnostic: dict[str, Any], artifact_dir: str | Path) -> Path:
    if diagnostic.get("artifact_type") != "evaluation_diagnostic":
        raise ValueError("Expected evaluation_diagnostic artifact")
    target_name, database, schema, agent_object = _identity_components(diagnostic)
    target = contained_path(
        artifact_dir,
        "diagnostics",
        target_name,
        database,
        schema,
        agent_object,
        diagnostic["suite"],
        f"{diagnostic['run_name']}.json",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Evaluation diagnostic already exists: {target}")
    target.write_text(json.dumps(diagnostic, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def validate_result(  # noqa: C901
    value: dict[str, Any], expected_type: str | None = None
) -> dict[str, Any]:
    if value.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ValueError(f"Evaluation artifact schema_version must be {ARTIFACT_SCHEMA_VERSION}")
    if value.get("plan_schema_version") != CURRENT_PLAN_SCHEMA_VERSION:
        raise ValueError(
            f"Evaluation artifact plan_schema_version must be {CURRENT_PLAN_SCHEMA_VERSION}"
        )
    artifact_type = value.get("artifact_type")
    if artifact_type not in {"candidate", "baseline"}:
        raise ValueError("Evaluation artifact_type must be candidate or baseline")
    if expected_type and artifact_type != expected_type:
        raise ValueError(f"Expected {expected_type} artifact, got {artifact_type!r}")
    required = {
        "agent",
        "suite",
        "eval_model",
        "run_name",
        "timestamp",
        "summary",
        "thresholds",
        "regression_tolerances",
        "passed",
        "total_records",
        "plan_schema_version",
        "suite_signature",
        "plan_identity",
        "agent_fqn",
        "dataset_fqn",
        "stage_fqn",
        "metric_names",
        "ordered_ground_truth_refs",
        "status",
    }
    missing = sorted(required - value.keys())
    if missing:
        raise ValueError(f"Evaluation artifact is missing required fields: {', '.join(missing)}")
    if not isinstance(value["summary"], dict) or not isinstance(
        value["ordered_ground_truth_refs"], list
    ):
        raise ValueError("Evaluation artifact summary must be an object and ordered refs a list")
    if any(not isinstance(ref, str) for ref in value["ordered_ground_truth_refs"]):
        raise ValueError("Evaluation artifact ordered refs must be strings")
    if len(value["ordered_ground_truth_refs"]) != len(set(value["ordered_ground_truth_refs"])):
        raise ValueError("Evaluation artifact ordered_ground_truth_refs must be unique")
    for field in ("agent", "suite", "eval_model", "run_name"):
        artifact_slug(value[field], f"evaluation artifact {field}")
    metadata = value.get("run_metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Evaluation artifact run_metadata must be an object")
    plan_identity = metadata.get("plan_identity")
    if not isinstance(plan_identity, dict) or plan_identity.get("agent_fqn") != value.get(
        "agent_fqn"
    ):
        raise ValueError("Evaluation artifact run_metadata.plan_identity must match agent_fqn")
    if value.get("plan_identity") != plan_identity:
        raise ValueError(
            "Evaluation artifact plan_identity must match signed run metadata identity"
        )
    expected_identity = {
        "agent_name": value.get("agent"),
        "suite_name": value.get("suite"),
        "eval_model": value.get("eval_model"),
        "agent_fqn": value.get("agent_fqn"),
        "dataset_fqn": value.get("dataset_fqn"),
        "stage_fqn": value.get("stage_fqn"),
    }
    if any(plan_identity.get(field) != expected for field, expected in expected_identity.items()):
        raise ValueError("Evaluation artifact fields must match signed plan_identity")
    for phase in ("pre_start", "post_completion"):
        provenance = metadata.get(phase)
        if not isinstance(provenance, dict) or not provenance.get("default_version"):
            raise ValueError(
                f"Evaluation artifact run_metadata.{phase} must include default_version"
            )
    if metadata.get("evaluated_version") != metadata["pre_start"]["default_version"]:
        raise ValueError("Evaluation artifact evaluated_version must equal pre-start DEFAULT")
    changed = (
        metadata["pre_start"]["default_version"] != metadata["post_completion"]["default_version"]
    )
    if metadata.get("default_version_changed") is not changed:
        raise ValueError("Evaluation artifact DEFAULT drift flag is inconsistent with provenance")
    if changed and (value.get("status") != "indeterminate" or value.get("passed") is not False):
        raise ValueError("Evaluation artifact with DEFAULT drift must be indeterminate and failed")
    _validate_dataset_binding(value)
    _validate_statistics(value)
    return value


def _validate_dataset_binding(value: dict[str, Any]) -> None:
    metadata = value["run_metadata"]
    if "dataset_snapshot" not in metadata and "dataset_source_changed" not in metadata:
        return
    snapshot = validate_snapshot(
        metadata.get("dataset_snapshot"), value["ordered_ground_truth_refs"]
    )
    changed = metadata.get("dataset_source_changed")
    if type(changed) is not bool:
        raise ValueError("Evaluation dataset_source_changed must be a boolean")
    if changed and (value.get("status") != "indeterminate" or value.get("passed") is not False):
        raise ValueError("Evaluation artifact with dataset drift must be indeterminate and failed")
    if value["artifact_type"] == "candidate":
        rows = value.get("results")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Evaluation candidate requires row evidence")
        annotated = [dict(row) for row in rows]
        annotate_rows(snapshot, annotated)
        if annotated != rows:
            raise ValueError("Evaluation result annotations do not match the dataset snapshot")


def _validate_statistics(value: dict[str, Any]) -> None:
    refs = value["ordered_ground_truth_refs"]
    if not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise ValueError("Evaluation artifact ordered refs must be non-empty strings")
    validate_metric_policy(
        value["metric_names"], value["thresholds"], value["regression_tolerances"]
    )
    total = value["total_records"]
    if type(total) is not int or total != len(refs):
        raise ValueError("Evaluation artifact total_records must equal the declared ref count")
    for metric, stats in value["summary"].items():
        if metric not in value["metric_names"] or not isinstance(stats, dict):
            raise ValueError("Evaluation summary must contain declared metric statistics")
        finite_number(stats.get("avg"), f"average for {metric}")
        count = stats.get("n")
        if type(count) is not int or not 0 < count <= total:
            raise ValueError(f"Evaluation summary count for {metric} is invalid")
        if metric not in TOOL_METRICS and count != total:
            raise ValueError(f"Evaluation summary count for {metric} is incomplete")
    if set(value["metric_names"]) - TOOL_METRICS - value["summary"].keys():
        raise ValueError("Evaluation summary is missing required metrics")
    if value["artifact_type"] == "candidate":
        rows = value.get("results")
        if not isinstance(rows, list):
            raise ValueError("Evaluation candidate requires row evidence")
        validate_observations(rows, refs, value["metric_names"])
        if compute_summary(rows) != value["summary"]:
            raise ValueError("Evaluation summary does not match row evidence")


def load_result(path: str | Path, expected_type: str | None = None) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Evaluation result must be a JSON object: {path}")
    return validate_result(value, expected_type)
