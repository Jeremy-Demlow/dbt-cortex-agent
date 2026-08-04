from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..artifacts import ARTIFACT_SCHEMA_VERSION, contained_path
from .results import validate_result

def build_baseline(candidate: dict[str, Any]) -> dict[str, Any]:
    validate_result(candidate, "candidate")
    if candidate.get("passed") is not True:
        raise ValueError("Failed evaluation candidates cannot become baselines")
    metadata = dict(candidate.get("run_metadata") or {})
    metadata.pop("git_sha", None)
    keys = (
        "agent", "suite", "eval_model", "run_name", "timestamp", "summary", "thresholds",
        "regression_tolerances", "passed", "total_records", "plan_schema_version",
        "suite_signature", "projection", "agent_fqn", "dataset_fqn", "stage_fqn",
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