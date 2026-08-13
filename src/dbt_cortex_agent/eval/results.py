from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..artifacts import ARTIFACT_SCHEMA_VERSION, artifact_slug, contained_path
from .dataset import TOOL_METRICS


def compute_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        name = row.get("metric_name")
        score = row.get("eval_agg_score")
        if not name or score is None:
            continue
        if name in TOOL_METRICS and row.get("test_type", "in_scope") != "in_scope":
            continue
        try:
            grouped.setdefault(str(name), []).append(float(score))
        except (TypeError, ValueError):
            continue
    return {
        name: {"avg": sum(scores) / len(scores), "n": len(scores)}
        for name, scores in sorted(grouped.items())
    }


def threshold_failures(summary: dict[str, dict[str, Any]], thresholds: dict[str, float]) -> list[str]:
    failures: list[str] = []
    for metric, threshold in thresholds.items():
        stats = summary.get(metric)
        if not stats or stats.get("avg") is None:
            failures.append(f"{metric}: missing threshold metric")
        elif float(stats["avg"]) < float(threshold):
            failures.append(f"{metric}: {float(stats['avg']):.3f} < {float(threshold):.3f}")
    return failures


def build_candidate(
    *, plan, run_name: str, rows: list[dict[str, Any]], provenance: dict[str, Any]
) -> dict[str, Any]:
    summary = compute_summary(rows)
    failures = threshold_failures(summary, plan.thresholds)
    drift = provenance.get("default_version_changed") is True
    if drift:
        failures.append("Agent DEFAULT version changed during evaluation; result is indeterminate")
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
        "status": "indeterminate" if drift else "completed",
        "threshold_failures": failures,
        "total_records": len({row.get("record_id") for row in rows if row.get("record_id")}),
        "ordered_ground_truth_refs": plan.ordered_ground_truth_refs,
        "results": rows,
    }


def write_candidate(candidate: dict[str, Any], artifact_dir: str | Path) -> Path:
    validate_result(candidate, "candidate")
    target = contained_path(
        artifact_dir,
        "candidates",
        candidate["agent"],
        candidate["suite"],
        f"{candidate['run_name']}.json",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(candidate, indent=2, default=str) + "\n", encoding="utf-8")
    return target


def write_diagnostic(diagnostic: dict[str, Any], artifact_dir: str | Path) -> Path:
    if diagnostic.get("artifact_type") != "evaluation_diagnostic":
        raise ValueError("Expected evaluation_diagnostic artifact")
    target = contained_path(
        artifact_dir,
        "diagnostics",
        diagnostic["agent"],
        diagnostic["suite"],
        f"{diagnostic['run_name']}.json",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(diagnostic, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def validate_result(value: dict[str, Any], expected_type: str | None = None) -> dict[str, Any]:
    if value.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ValueError(
            f"Evaluation artifact schema_version must be {ARTIFACT_SCHEMA_VERSION}"
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
    if not isinstance(value["summary"], dict) or not isinstance(value["ordered_ground_truth_refs"], list):
        raise ValueError("Evaluation artifact summary must be an object and ordered refs a list")
    if len(value["ordered_ground_truth_refs"]) != len(set(value["ordered_ground_truth_refs"])):
        raise ValueError("Evaluation artifact ordered_ground_truth_refs must be unique")
    for field in ("agent", "suite", "eval_model", "run_name"):
        artifact_slug(value[field], f"evaluation artifact {field}")
    metadata = value.get("run_metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Evaluation artifact run_metadata must be an object")
    plan_identity = metadata.get("plan_identity")
    if not isinstance(plan_identity, dict) or plan_identity.get("agent_fqn") != value.get("agent_fqn"):
        raise ValueError("Evaluation artifact run_metadata.plan_identity must match agent_fqn")
    if value.get("plan_identity") != plan_identity:
        raise ValueError("Evaluation artifact plan_identity must match signed run metadata identity")
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
            raise ValueError(f"Evaluation artifact run_metadata.{phase} must include default_version")
    if metadata.get("evaluated_version") != metadata["pre_start"]["default_version"]:
        raise ValueError("Evaluation artifact evaluated_version must equal pre-start DEFAULT")
    changed = metadata["pre_start"]["default_version"] != metadata["post_completion"]["default_version"]
    if metadata.get("default_version_changed") is not changed:
        raise ValueError("Evaluation artifact DEFAULT drift flag is inconsistent with provenance")
    if changed and (value.get("status") != "indeterminate" or value.get("passed") is not False):
        raise ValueError("Evaluation artifact with DEFAULT drift must be indeterminate and failed")
    return value


def load_result(path: str | Path, expected_type: str | None = None) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Evaluation result must be a JSON object: {path}")
    return validate_result(value, expected_type)