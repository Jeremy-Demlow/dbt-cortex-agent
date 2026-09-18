from __future__ import annotations

from typing import Any

from ..domain import finite_number

TOOL_METRICS = {"tool_selection_accuracy", "tool_execution_accuracy"}
DatasetSnapshot = tuple[tuple[str, str, str], ...]


def metric_names(metrics: list[Any]) -> list[str]:
    names: list[str] = []
    for metric in metrics:
        if isinstance(metric, str):
            name = metric
        elif isinstance(metric, dict) and metric.get("name"):
            name = str(metric["name"])
            ranges = metric.get("score_ranges")
            if ranges is not None and set(ranges) != {"min_score", "median_score", "max_score"}:
                raise ValueError(f"Custom metric {name!r} must define all three score_ranges")
            if not str(metric.get("prompt") or "").strip():
                raise ValueError(f"Custom metric {name!r} requires a prompt")
        else:
            raise ValueError(f"Invalid metric declaration: {metric!r}")
        if not name.strip():
            raise ValueError("Metric names must not be empty")
        names.append(name)
    if not names:
        raise ValueError("Evaluation suite must declare at least one metric")
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Evaluation metric names must be unique: {', '.join(duplicates)}")
    return names


def validate_eval_meta(
    meta: dict[str, Any],
) -> tuple[list[str], dict[str, float], dict[str, float]]:
    names = metric_names(list(meta.get("metrics") or []))
    thresholds, tolerances = validate_metric_policy(
        names, meta.get("thresholds") or {}, meta.get("regression_tolerances") or {}
    )
    return names, thresholds, tolerances


def validate_metric_policy(
    names: list[str], thresholds: Any, tolerances: Any
) -> tuple[dict[str, float], dict[str, float]]:
    if (
        not isinstance(names, list)
        or not names
        or any(not isinstance(name, str) or not name.strip() for name in names)
        or len(names) != len(set(names))
    ):
        raise ValueError("Evaluation metric_names must be non-empty and unique strings")
    thresholds = _numeric_map(thresholds, "threshold")
    tolerances = _numeric_map(tolerances, "regression tolerance")
    unknown = sorted((set(thresholds) | set(tolerances)) - set(names))
    if unknown:
        raise ValueError(f"Gates reference undeclared metrics: {', '.join(unknown)}")
    return thresholds, tolerances


def _numeric_map(raw: Any, label: str) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise ValueError(f"Evaluation {label} policy must be an object")
    values: dict[str, float] = {}
    for name, value in raw.items():
        number = finite_number(value, f"{label} for {name!r}")
        if number < 0:
            raise ValueError(f"Invalid {label} for {name!r}: must be non-negative")
        values[str(name)] = number
    return values


def validate_table(
    cursor, table_fqn: str, metrics: list[str], ordered_ground_truth_refs: list[str]
) -> DatasetSnapshot:
    cursor.execute(f"DESCRIBE TABLE {table_fqn}")
    columns = {str(row[0]).upper() for row in cursor.fetchall()}
    missing = {"INPUT_QUERY", "OUTPUT"} - columns
    if missing:
        raise ValueError(f"Eval table {table_fqn} is missing columns: {', '.join(sorted(missing))}")
    cursor.execute(f"SELECT COUNT(*) FROM {table_fqn}")
    count = int(cursor.fetchone()[0])
    if count == 0:
        raise ValueError(f"Eval table {table_fqn} is empty")
    snapshot = read_snapshot(cursor, table_fqn, ordered_ground_truth_refs)
    if len(snapshot) != count:
        raise ValueError(f"Eval table {table_fqn} cardinality changed during validation")
    if "answer_correctness" in metrics:
        cursor.execute(
            f"SELECT COUNT(*) FROM {table_fqn} "
            "WHERE output:ground_truth_output IS NULL "
            "OR TRIM(output:ground_truth_output::STRING) = ''"
        )
        missing_output = int(cursor.fetchone()[0])
        if missing_output:
            raise ValueError(
                f"Eval table {table_fqn} has {missing_output} row(s) missing ground_truth_output"
            )
    if TOOL_METRICS & set(metrics):
        cursor.execute(
            f"SELECT COUNT(*) FROM {table_fqn} "
            "WHERE (output:ground_truth_invocations IS NULL "
            "OR ARRAY_SIZE(output:ground_truth_invocations) = 0) "
            "AND COALESCE(output:custom_criteria:test_type::STRING, 'in_scope') = 'in_scope'"
        )
        missing_tools = int(cursor.fetchone()[0])
        if missing_tools:
            raise ValueError(
                f"Eval table {table_fqn} has {missing_tools} in-scope row(s) missing "
                "ground_truth_invocations"
            )
    return snapshot


def validate_snapshot(source_rows: Any, ordered_ground_truth_refs: list[str]) -> DatasetSnapshot:
    if not isinstance(source_rows, (list, tuple)) or not source_rows:
        raise ValueError("Evaluation dataset snapshot must contain source rows")
    for row in source_rows:
        if (
            not isinstance(row, (list, tuple))
            or len(row) != 3
            or any(not isinstance(value, str) or not value.strip() for value in row)
        ):
            raise ValueError("Evaluation dataset snapshot requires nonblank input/test_type/ref")
    inputs = [row[0] for row in source_rows]
    refs = [row[2] for row in source_rows]
    if len(inputs) != len(set(inputs)):
        raise ValueError("Evaluation dataset snapshot has duplicate INPUT_QUERY values")
    if len(refs) != len(set(refs)):
        raise ValueError("Evaluation dataset snapshot has duplicate ground_truth_ref values")
    if set(refs) != set(ordered_ground_truth_refs) or len(refs) != len(ordered_ground_truth_refs):
        raise ValueError("Evaluation dataset snapshot ground_truth_ref content differs from plan")
    return tuple(sorted((row[0], row[1], row[2]) for row in source_rows))


def read_snapshot(cursor, table_fqn: str, ordered_ground_truth_refs: list[str]) -> DatasetSnapshot:
    cursor.execute(
        f"SELECT input_query, "
        "COALESCE(output:custom_criteria:test_type::STRING, 'in_scope'), "
        f"output:custom_criteria:ground_truth_ref::STRING FROM {table_fqn}"
    )
    return validate_snapshot(cursor.fetchall(), ordered_ground_truth_refs)


def annotate_rows(snapshot: DatasetSnapshot, rows: list[dict[str, Any]]) -> None:
    mapping = {
        input_query: (test_type, reference) for input_query, test_type, reference in snapshot
    }
    for row in rows:
        input_query = row.get("input")
        if not isinstance(input_query, str) or input_query not in mapping:
            raise ValueError("Evaluation result input is absent from the dataset snapshot")
        test_type, reference = mapping[input_query]
        row["test_type"] = test_type
        row["ground_truth_ref"] = reference
