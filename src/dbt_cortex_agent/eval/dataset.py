from __future__ import annotations

from typing import Any


TOOL_METRICS = {"tool_selection_accuracy", "tool_execution_accuracy"}


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


def validate_eval_meta(meta: dict[str, Any]) -> tuple[list[str], dict[str, float], dict[str, float]]:
    names = metric_names(list(meta.get("metrics") or []))
    thresholds = _numeric_map(meta.get("thresholds"), "threshold")
    tolerances = _numeric_map(meta.get("regression_tolerances"), "regression tolerance")
    unknown = sorted((set(thresholds) | set(tolerances)) - set(names))
    if unknown:
        raise ValueError(f"Gates reference undeclared metrics: {', '.join(unknown)}")
    return names, thresholds, tolerances


def _numeric_map(raw: Any, label: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for name, value in (raw or {}).items():
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid {label} for {name!r}: {value!r}") from exc
        if number < 0:
            raise ValueError(f"Invalid {label} for {name!r}: must be non-negative")
        values[str(name)] = number
    return values


def validate_table(
    cursor, table_fqn: str, metrics: list[str], ordered_ground_truth_refs: list[str]
) -> int:
    cursor.execute(f"DESCRIBE TABLE {table_fqn}")
    columns = {str(row[0]).upper() for row in cursor.fetchall()}
    missing = {"INPUT_QUERY", "OUTPUT"} - columns
    if missing:
        raise ValueError(f"Eval table {table_fqn} is missing columns: {', '.join(sorted(missing))}")
    cursor.execute(f"SELECT COUNT(*) FROM {table_fqn}")
    count = int(cursor.fetchone()[0])
    if count == 0:
        raise ValueError(f"Eval table {table_fqn} is empty")
    cursor.execute(
        f"SELECT input_query, output:custom_criteria:ground_truth_ref::STRING "
        f"FROM {table_fqn}"
    )
    identity_rows = [(str(row[0]), None if row[1] is None else str(row[1])) for row in cursor.fetchall()]
    inputs = [row[0] for row in identity_rows]
    refs = [row[1] for row in identity_rows]
    duplicate_inputs = sorted({value for value in inputs if inputs.count(value) > 1})
    duplicate_refs = sorted({value for value in refs if value is not None and refs.count(value) > 1})
    if duplicate_inputs:
        raise ValueError(f"Eval table {table_fqn} has duplicate INPUT_QUERY values")
    if any(ref is None or not ref for ref in refs):
        raise ValueError(f"Eval table {table_fqn} has missing ground_truth_ref values")
    if duplicate_refs:
        raise ValueError(f"Eval table {table_fqn} has duplicate ground_truth_ref values")
    if set(refs) != set(ordered_ground_truth_refs) or len(refs) != len(ordered_ground_truth_refs):
        raise ValueError(
            f"Eval table {table_fqn} ground_truth_ref content does not match the dbt execution plan"
        )
    if "answer_correctness" in metrics:
        cursor.execute(
            f"SELECT COUNT(*) FROM {table_fqn} "
            "WHERE output:ground_truth_output IS NULL "
            "OR TRIM(output:ground_truth_output::STRING) = ''"
        )
        missing_output = int(cursor.fetchone()[0])
        if missing_output:
            raise ValueError(f"Eval table {table_fqn} has {missing_output} row(s) missing ground_truth_output")
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
                f"Eval table {table_fqn} has {missing_tools} in-scope row(s) missing ground_truth_invocations"
            )
    return count


def annotate_rows(cursor, table_fqn: str, rows: list[dict[str, Any]]) -> None:
    cursor.execute(
        f"SELECT input_query, "
        "COALESCE(output:custom_criteria:test_type::STRING, 'in_scope'), "
        f"output:custom_criteria:ground_truth_ref::STRING FROM {table_fqn}"
    )
    source_rows = cursor.fetchall()
    mapping = {str(row[0]): (str(row[1]), str(row[2])) for row in source_rows}
    if len(mapping) != len(source_rows):
        raise ValueError(f"Eval table {table_fqn} contains ambiguous duplicate INPUT_QUERY values")
    for row in rows:
        input_query = str(row.get("input"))
        if input_query not in mapping:
            raise ValueError(f"Evaluation result input is absent from {table_fqn}: {input_query!r}")
        test_type, reference = mapping[input_query]
        row["test_type"] = test_type
        row["ground_truth_ref"] = reference