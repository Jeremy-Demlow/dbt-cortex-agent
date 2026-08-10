from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from ..artifacts import ARTIFACT_SCHEMA_VERSION, contained_path
from .results import validate_result


def _legacy_summary(value: Any) -> dict[str, dict[str, float | int]]:
    if not isinstance(value, dict) or not value:
        raise ValueError("Legacy accepted artifact summary must be a non-empty object")
    summary: dict[str, dict[str, float | int]] = {}
    for metric, raw in value.items():
        if not isinstance(raw, dict) or "avg" not in raw:
            raise ValueError("Legacy accepted artifact summary entries must include avg")
        try:
            stats: dict[str, float | int] = {"avg": float(raw["avg"])}
            if "n" in raw:
                stats["n"] = int(raw["n"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Legacy accepted artifact summary values must be numeric") from exc
        if not math.isfinite(float(stats["avg"])) or int(stats.get("n", 0)) < 0:
            raise ValueError("Legacy accepted artifact summary values must be finite and non-negative")
        summary[str(metric)] = stats
    return summary


def build_migrated_baseline(legacy: dict[str, Any], plan, source: str | Path) -> dict[str, Any]:
    if legacy.get("schema_version") not in (None, 1):
        raise ValueError("Legacy accepted artifact schema_version must be absent or 1")
    if legacy.get("artifact_type") not in (None, "baseline") or legacy.get("passed") is not True:
        raise ValueError("Legacy artifact must be an accepted passing baseline")
    legacy_agent = legacy.get("agent")
    if isinstance(legacy_agent, str) and legacy_agent.upper().rsplit(".", 1)[-1].endswith("_EVAL"):
        raise ValueError(
            "Legacy _EVAL Agent identity is incompatible with the single-Agent evaluation plan"
        )
    if legacy_agent not in {plan.agent_name, plan.agent_fqn.rsplit(".", 1)[-1], plan.agent_fqn}:
        raise ValueError("Legacy artifact agent does not match the dbt evaluation plan")
    if legacy.get("suite") not in (None, plan.suite_name):
        raise ValueError("Legacy artifact suite does not match the dbt evaluation plan")
    run_name = legacy.get("run_name")
    timestamp = legacy.get("timestamp")
    metadata = legacy.get("run_metadata")
    if not isinstance(run_name, str) or not run_name or not isinstance(timestamp, str) or not timestamp:
        raise ValueError("Legacy accepted artifact requires run_name and timestamp")
    if not isinstance(metadata, dict):
        raise ValueError("Legacy accepted artifact run_metadata must be an object")
    summary = _legacy_summary(legacy.get("summary"))
    if set(summary) != set(plan.metric_names):
        raise ValueError("Legacy summary metric set must match the current dbt evaluation plan")
    version = str(
        metadata.get("evaluated_version")
        or (metadata.get("pre_start") or {}).get("default_version")
        or "LEGACY_UNKNOWN"
    )
    provenance = {
        "agent_fqn": plan.agent_fqn,
        "plan_identity": plan.plan_identity,
        "evaluated_version": version,
        "pre_start": {"default_version": version, "aliases": {}},
        "post_completion": {"default_version": version, "aliases": {}},
        "default_version_changed": False,
        "legacy_migration": {
            "source": Path(source).name,
            "schema_version": legacy.get("schema_version"),
            "artifact_type": legacy.get("artifact_type"),
            "run_name": run_name,
            "timestamp": timestamp,
            "run_metadata": metadata,
        },
    }
    baseline = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "baseline",
        "agent": plan.agent_name,
        "suite": plan.suite_name,
        "eval_model": plan.eval_model,
        "run_name": run_name,
        "timestamp": timestamp,
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
        "passed": True,
        "status": "completed",
        "total_records": int(legacy.get("total_records", 0)),
        "ordered_ground_truth_refs": plan.ordered_ground_truth_refs,
    }
    validate_result(baseline, "baseline")
    return baseline


def migrate_legacy_baseline(
    source: str | Path,
    plan,
    baseline_dir: str | Path,
    *,
    apply: bool = False,
    force: bool = False,
) -> tuple[dict[str, Any], Path]:
    source_path = Path(source)
    legacy = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(legacy, dict):
        raise ValueError("Legacy accepted artifact must be a JSON object")
    baseline = build_migrated_baseline(legacy, plan, source_path)
    target = contained_path(baseline_dir, baseline["agent"], f"{baseline['suite']}.json")
    if apply and target.exists() and not force:
        raise FileExistsError(f"Baseline already exists: {target}; use --force only after review")
    if apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(baseline, indent=2, default=str) + "\n", encoding="utf-8")
    return baseline, target

def build_baseline(candidate: dict[str, Any]) -> dict[str, Any]:
    validate_result(candidate, "candidate")
    if candidate.get("passed") is not True:
        raise ValueError("Failed evaluation candidates cannot become baselines")
    metadata = dict(candidate.get("run_metadata") or {})
    metadata.pop("git_sha", None)
    keys = (
        "agent", "suite", "eval_model", "run_name", "timestamp", "summary", "thresholds",
        "regression_tolerances", "passed", "total_records", "plan_schema_version",
        "suite_signature", "plan_identity", "agent_fqn", "dataset_fqn", "stage_fqn",
        "metric_names", "ordered_ground_truth_refs", "status",
    )
    baseline = {key: candidate.get(key) for key in keys}
    baseline["schema_version"] = ARTIFACT_SCHEMA_VERSION
    baseline["artifact_type"] = "baseline"
    baseline["run_metadata"] = metadata
    validate_result(baseline, "baseline")
    return baseline


def accept_baseline(
    candidate: dict[str, Any], baseline_dir: str | Path, *, force: bool = False
) -> Path:
    baseline = build_baseline(candidate)
    target = contained_path(
        baseline_dir, baseline["agent"], f"{baseline['suite']}.json"
    )
    if target.exists() and not force:
        raise FileExistsError(f"Baseline already exists: {target}; use --force after recording the ratchet decision")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(baseline, indent=2, default=str) + "\n", encoding="utf-8")
    return target