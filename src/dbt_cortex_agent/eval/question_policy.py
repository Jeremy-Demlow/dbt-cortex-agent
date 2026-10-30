from __future__ import annotations

from typing import Any

from ..domain import finite_number
from .dataset import SYSTEM_METRICS, TOOL_METRICS, DatasetSnapshot


def _score(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    return finite_number(value, label)


def metric_bounds(metrics: list[Any], selected: set[str]) -> dict[str, list[float]]:
    bounds = {}
    declarations = {item if isinstance(item, str) else item["name"]: item for item in metrics}
    for name in sorted(selected):
        if name in SYSTEM_METRICS:
            bounds[name] = [0.0, 1.0]
            continue
        declaration = declarations.get(name)
        ranges = declaration.get("score_ranges") if isinstance(declaration, dict) else None
        if not isinstance(ranges, dict) or set(ranges) != {
            "min_score",
            "median_score",
            "max_score",
        }:
            raise ValueError(f"Question floor metric {name} requires explicit score_ranges")
        values: list[float] = []
        for key in ("min_score", "median_score", "max_score"):
            pair = ranges[key]
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError(f"Question floor metric {name} requires two-value score ranges")
            values.extend(_score(value, f"score_ranges for {name}") for value in pair)
        if values != sorted(values):
            raise ValueError(f"Question floor metric {name} requires ordered score ranges")
        bounds[name] = [values[0], values[-1]]
    return bounds


def _protected_metrics(floors: Any, types: Any, refs: list[str], names: list[str]) -> set[str]:
    if not isinstance(floors, dict) or not floors or set(floors) - set(refs):
        raise ValueError("Question policy requires declared ground-truth refs")
    if not isinstance(types, dict) or set(types) != set(floors):
        raise ValueError("Question policy test_types must match protected refs")
    selected: set[str] = set()
    for reference, thresholds in floors.items():
        if not isinstance(thresholds, dict) or not thresholds or set(thresholds) - set(names):
            raise ValueError("Question floors must name declared metrics")
        test_type = types[reference]
        if not isinstance(test_type, str) or not test_type.strip():
            raise ValueError("Question policy requires nonblank test types")
        if set(thresholds) & TOOL_METRICS and test_type != "in_scope":
            raise ValueError("Question tool floors require in_scope questions")
        selected.update(thresholds)
    return selected


def _validate_bounds(bounds: Any, selected: set[str]) -> None:
    if not isinstance(bounds, dict) or set(bounds) != selected:
        raise ValueError("Question policy score_bounds must match protected metrics")
    for name, pair in bounds.items():
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Question policy requires two-value score bounds")
        lower, upper = (_score(value, f"score bounds for {name}") for value in pair)
        if lower > upper or (name in SYSTEM_METRICS and pair != [0, 1]):
            raise ValueError(f"Invalid question policy score bounds for {name}")


def validate_question_policy(
    policy: Any, refs: list[str], names: list[str], metrics: list[Any] | None = None
) -> dict[str, Any]:
    if (
        not isinstance(policy, dict)
        or set(policy) != {"schema_version", "thresholds", "score_bounds", "test_types"}
        or type(policy["schema_version"]) is not int
        or policy["schema_version"] != 1
    ):
        raise ValueError("Invalid question_policy schema")
    floors, bounds, types = (policy[key] for key in ("thresholds", "score_bounds", "test_types"))
    selected = _protected_metrics(floors, types, refs, names)
    _validate_bounds(bounds, selected)
    if metrics is not None and bounds != metric_bounds(metrics, selected):
        raise ValueError("Question policy score bounds differ from metric declarations")
    for thresholds in floors.values():
        for name, value in thresholds.items():
            floor = _score(value, f"question threshold for {name}")
            if not bounds[name][0] <= floor <= bounds[name][1]:
                raise ValueError(f"Question threshold for {name} is outside score bounds")
    return policy


def validate_question_snapshot(policy: dict[str, Any], snapshot: DatasetSnapshot) -> None:
    types = {reference: test_type for _, test_type, reference in snapshot}
    for reference, expected in policy.get("test_types", {}).items():
        if types.get(reference) != expected:
            raise ValueError(f"Question policy test_type differs from dataset for {reference}")


def question_failures(rows: list[dict[str, Any]], policy: dict[str, Any]) -> list[str]:
    observations = {(row["ground_truth_ref"], row["metric_name"]): row for row in rows}
    failures = []
    for reference, thresholds in policy["thresholds"].items():
        for name, floor in thresholds.items():
            row = observations.get((reference, name))
            if row is None:
                raise ValueError(f"Missing question floor observation: {reference}/{name}")
            if row.get("test_type", "in_scope") != policy["test_types"][reference]:
                raise ValueError(f"Question policy test_type differs from evidence for {reference}")
            score = finite_number(row.get("eval_agg_score"), f"score for {reference}/{name}")
            lower, upper = policy["score_bounds"][name]
            if not lower <= score <= upper:
                raise ValueError(f"Question score for {reference}/{name} is outside score bounds")
            if score < floor:
                failures.append(f"question {reference}/{name}: {score:.3f} < {floor:.3f}")
    return failures
