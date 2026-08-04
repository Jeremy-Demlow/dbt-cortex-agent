from __future__ import annotations

from typing import Any

from .results import threshold_failures, validate_result


def metric_averages(result: dict[str, Any]) -> dict[str, float]:
    return {
        name: float(stats["avg"])
        for name, stats in (result.get("summary") or {}).items()
        if isinstance(stats, dict) and stats.get("avg") is not None
    }


def suite_change(baseline: dict[str, Any], candidate: dict[str, Any]) -> str | None:
    if baseline.get("ordered_ground_truth_refs") != candidate.get("ordered_ground_truth_refs"):
        return "ordered ground-truth refs changed"
    if baseline.get("metric_names") != candidate.get("metric_names"):
        return "metric contract changed"
    if baseline.get("thresholds") != candidate.get("thresholds"):
        return "threshold policy changed"
    if baseline.get("regression_tolerances") != candidate.get("regression_tolerances"):
        return "regression tolerance policy changed"
    if baseline.get("suite_signature") != candidate.get("suite_signature"):
        return "suite signature changed"
    return None


def compare_results(
    baseline: dict[str, Any], candidate: dict[str, Any], default_tolerance: float = 0.01
) -> dict[str, Any]:
    validate_result(baseline, "baseline")
    validate_result(candidate, "candidate")
    reason = suite_change(baseline, candidate)
    before, after = metric_averages(baseline), metric_averages(candidate)
    tolerances = {
        name: float(value)
        for name, value in (baseline.get("regression_tolerances") or {}).items()
    }
    gated = set(baseline.get("thresholds") or {}) | set(tolerances)
    rows: list[dict[str, Any]] = []
    regressions: list[str] = []
    for metric in sorted(set(before) | set(after)):
        old, new = before.get(metric), after.get(metric)
        tolerance = tolerances.get(metric, default_tolerance)
        delta = None if old is None or new is None else new - old
        status = "new" if old is None else "missing" if new is None else "flat"
        if old is not None and new is None and metric in gated:
            status = "regressed"
        elif delta is not None and delta < -tolerance:
            status = "regressed" if metric in gated else "advisory"
        elif delta is not None and delta > tolerance:
            status = "improved"
        if status == "regressed":
            regressions.append(metric)
        rows.append({
            "metric": metric, "baseline": old, "candidate": new, "delta": delta,
            "tolerance": tolerance, "status": status,
        })
    failures = threshold_failures(candidate.get("summary") or {}, candidate.get("thresholds") or {})
    return {
        "passed": reason is None and not regressions and not failures,
        "suite_change": reason,
        "regressions": regressions,
        "threshold_failures": failures,
        "metrics": rows,
    }