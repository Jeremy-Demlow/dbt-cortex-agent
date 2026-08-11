from __future__ import annotations

import json
import hashlib
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..config import Config
from ..dbt_runner import CommandRunner, run_dbt_operation, run_dbt_parse
from ..identifiers import fqn, identifier
from ..skills import assert_apply_safety
from .dataset import annotate_rows, validate_table
from .results import build_candidate, write_candidate


TERMINAL_SUCCESS = {"COMPLETED", "SUCCEEDED", "DONE"}
TERMINAL_FAILURE = {"FAILED", "ERROR", "CANCELLED", "INVOCATION_FAILED", "INVOCATION_ERROR"}
RETRYABLE_DETAILS = (
    "invocation failed",
    "service is currently unavailable",
    "internal error",
    "timed out",
    "timeout",
    "rate limit",
)
_PATH_COMPONENT = re.compile(r"^[A-Za-z0-9_$.-]+$")
PLAN_SCHEMA_VERSION = 1
_PLAN_PREFIX = "CORTEX_EVAL_PLAN_JSON="


@dataclass(frozen=True)
class EvalPlan:
    schema_version: int
    agent_name: str
    suite_name: str
    eval_model: str
    table_fqn: str
    agent_fqn: str
    stage_fqn: str
    target_name: str
    target_role: str
    target_database: str
    target_schema: str
    target_warehouse: str | None
    native_eval_config: dict[str, Any]
    dataset_name_token: str
    config_filename_template: str
    metric_names: list[str]
    thresholds: dict[str, float]
    regression_tolerances: dict[str, float]
    ordered_ground_truth_refs: list[str]
    suite_signature: str
    plan_identity: dict[str, Any]


@dataclass(frozen=True)
class PollResult:
    status: str
    details: str

    @property
    def succeeded(self) -> bool:
        return self.status in TERMINAL_SUCCESS


def _numeric_policy(raw: Any, label: str) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise ValueError(f"Evaluation plan {label} must be an object")
    try:
        values = {str(name): float(value) for name, value in raw.items()}
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Evaluation plan {label} values must be numeric") from exc
    if any(value < 0 for value in values.values()):
        raise ValueError(f"Evaluation plan {label} values must be non-negative")
    return values


def _plan_from_payload(payload: dict[str, Any], agent_name: str, suite_name: str) -> EvalPlan:
    if payload.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise ValueError(f"Evaluation plan schema_version must be {PLAN_SCHEMA_VERSION}")
    identity = payload.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("Evaluation plan identity must be an object")
    required_identity = {
        "agent_name", "suite_name", "eval_model", "agent_fqn",
        "dataset_fqn", "stage_fqn", "target_name", "target_role", "target_database",
        "target_schema",
    }
    missing_identity = sorted(required_identity - identity.keys())
    if missing_identity:
        raise ValueError(
            f"Evaluation plan identity is missing required fields: {', '.join(missing_identity)}"
        )
    if identity.get("agent_name") != agent_name or identity.get("suite_name") != suite_name:
        raise ValueError("Evaluation plan identity does not match the selected Agent and suite")
    if "projection" in identity or "projection" in payload:
        raise ValueError("Evaluation plan must not contain projection identity")
    signature_material = payload.get("signature_material")
    if not isinstance(signature_material, str):
        raise ValueError("Evaluation plan signature_material must be a string")
    expected_signature = hashlib.md5(signature_material.encode("utf-8")).hexdigest()
    if payload.get("suite_signature") != expected_signature:
        raise ValueError("Evaluation plan suite_signature does not match signature_material")
    try:
        signed = json.loads(signature_material)
    except json.JSONDecodeError as exc:
        raise ValueError("Evaluation plan signature_material is not valid JSON") from exc
    signed_fields = {
        "plan_schema_version": payload["schema_version"],
        "identity": identity,
        "native_eval_config": payload.get("native_eval_config"),
        "metric_names": payload.get("metric_names"),
        "thresholds": payload.get("thresholds"),
        "regression_tolerances": payload.get("regression_tolerances"),
        "ordered_ground_truth_refs": payload.get("ordered_ground_truth_refs"),
    }
    if signed != signed_fields:
        raise ValueError("Evaluation plan signed fields do not match signature_material")
    config_template = payload.get("native_eval_config")
    refs = payload.get("ordered_ground_truth_refs")
    metric_names = payload.get("metric_names")
    if not isinstance(config_template, dict) or not isinstance(refs, list) or not isinstance(metric_names, list):
        raise ValueError("Evaluation plan config, metric_names, and ordered refs have invalid types")
    config_agent = (
        config_template.get("evaluation", {}).get("agent_params", {}).get("agent_name")
    )
    if config_agent != identity.get("agent_fqn"):
        raise ValueError("Evaluation plan native config Agent must match signed agent_fqn")
    refs = [str(value) for value in refs]
    if not refs or any(not value for value in refs) or len(refs) != len(set(refs)):
        raise ValueError("Evaluation plan ordered_ground_truth_refs must be non-empty and unique")
    metric_names = [str(value) for value in metric_names]
    if not metric_names or len(metric_names) != len(set(metric_names)):
        raise ValueError("Evaluation plan metric_names must be non-empty and unique")
    token = payload.get("dataset_name_token")
    filename_template = payload.get("config_filename_template")
    if not isinstance(token, str) or not token or not isinstance(filename_template, str):
        raise ValueError("Evaluation plan dataset token and config filename template are required")
    if not identity.get("target_role"):
        raise ValueError("Evaluation plan target_role is required")
    return EvalPlan(
        schema_version=PLAN_SCHEMA_VERSION,
        agent_name=agent_name,
        suite_name=suite_name,
        eval_model=str(identity["eval_model"]),
        table_fqn=fqn(str(identity["dataset_fqn"]), "eval table"),
        agent_fqn=fqn(str(identity["agent_fqn"]), "Agent object"),
        stage_fqn=fqn(str(identity["stage_fqn"]), "evaluation stage"),
        target_name=str(identity["target_name"]),
        target_role=identifier(str(identity["target_role"]), "target role"),
        target_database=identifier(str(identity["target_database"]), "target database"),
        target_schema=identifier(str(identity["target_schema"]), "target schema"),
        target_warehouse=(str(identity["target_warehouse"]) if identity.get("target_warehouse") else None),
        native_eval_config=config_template,
        dataset_name_token=token,
        config_filename_template=filename_template,
        metric_names=metric_names,
        thresholds=_numeric_policy(payload.get("thresholds"), "thresholds"),
        regression_tolerances=_numeric_policy(payload.get("regression_tolerances"), "regression_tolerances"),
        ordered_ground_truth_refs=refs,
        suite_signature=expected_signature,
        plan_identity=dict(identity),
    )


def _extract_plan(stdout: str, agent_name: str, suite_name: str) -> EvalPlan:
    payloads = [line.split(_PLAN_PREFIX, 1)[1].strip() for line in stdout.splitlines() if _PLAN_PREFIX in line]
    if len(payloads) != 1:
        raise ValueError(f"Expected exactly one dbt evaluation plan payload, found {len(payloads)}")
    try:
        payload = json.loads(payloads[0])
    except json.JSONDecodeError as exc:
        raise ValueError("dbt evaluation plan payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("dbt evaluation plan payload must be a JSON object")
    return _plan_from_payload(payload, agent_name, suite_name)


def build_plan(
    config: Config,
    *,
    agent_name: str,
    suite_name: str,
    parse: bool = True,
    runner: CommandRunner | None = None,
    plan_payload: dict[str, Any] | None = None,
) -> EvalPlan:
    if plan_payload is not None:
        return _plan_from_payload(plan_payload, agent_name, suite_name)
    command_runner = runner or CommandRunner()
    if parse:
        parsed = run_dbt_parse(config.dbt_executable, config.project_dir, config.target, command_runner)
        if parsed.returncode != 0:
            raise RuntimeError(parsed.stderr.strip() or parsed.stdout.strip() or "dbt parse failed")
    rendered = run_dbt_operation(
        config.dbt_executable,
        config.project_dir,
        config.target,
        "dbt_cortex_agent.cortex_eval__execution_plan",
        {"agent_name": agent_name, "suite_name": suite_name},
        command_runner,
    )
    if rendered.returncode != 0:
        raise RuntimeError(rendered.stderr.strip() or rendered.stdout.strip() or "dbt evaluation plan render failed")
    return _extract_plan(rendered.stdout, agent_name, suite_name)


def render_eval_config(plan: EvalPlan, dataset_name: str) -> str:
    rendered = json.dumps(plan.native_eval_config, separators=(",", ":"))
    if rendered.count(plan.dataset_name_token) != 2:
        raise ValueError("dbt evaluation plan must contain exactly two dataset-name tokens")
    return rendered.replace(plan.dataset_name_token, dataset_name)


def flatten_status_details(raw: Any) -> str:
    if raw in (None, ""):
        return ""
    if isinstance(raw, (list, tuple)):
        return "; ".join(str(item) for item in raw if item)
    text = str(raw).strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return "; ".join(str(item) for item in parsed if item)
        except json.JSONDecodeError:
            pass
    return text


def is_retryable(details: Any) -> bool:
    value = flatten_status_details(details).lower()
    return bool(value) and any(pattern in value for pattern in RETRYABLE_DETAILS)


def poll(
    cursor,
    run_name: str,
    config_path: str,
    *,
    attempts: int,
    interval: float,
    sleep: Callable[[float], None] = time.sleep,
) -> PollResult:
    if attempts < 1:
        raise ValueError("Poll attempts must be at least 1")
    for attempt in range(attempts):
        cursor.execute(
            "CALL EXECUTE_AI_EVALUATION('STATUS', OBJECT_CONSTRUCT('run_name', %s), %s)",
            (run_name, config_path),
        )
        rows = cursor.fetchall()
        if rows:
            columns = [str(item[0]).upper() for item in cursor.description]
            row = rows[0]
            status = str(row[columns.index("STATUS")] if "STATUS" in columns else row[3]).upper()
            details = flatten_status_details(
                row[columns.index("STATUS_DETAILS")] if "STATUS_DETAILS" in columns else row[4] if len(row) > 4 else ""
            )
            if status in TERMINAL_SUCCESS | TERMINAL_FAILURE:
                return PollResult(status, details)
        if attempt + 1 < attempts:
            sleep(interval)
    return PollResult("TIMEOUT", "poll attempts exhausted")


def _upload_config(cursor, plan: EvalPlan, filename: str, content: str) -> str:
    if not _PATH_COMPONENT.fullmatch(filename):
        raise ValueError(f"Invalid evaluation config filename: {filename!r}")
    cursor.execute(f"CREATE STAGE IF NOT EXISTS {plan.stage_fqn}")
    cursor.execute(
        f"COPY INTO @{plan.stage_fqn}/{filename} FROM (SELECT %s) "
        "FILE_FORMAT=(TYPE=CSV FIELD_DELIMITER=NONE RECORD_DELIMITER=NONE COMPRESSION=NONE) "
        "SINGLE=TRUE OVERWRITE=TRUE",
        (content,),
    )
    return f"@{plan.stage_fqn}/{filename}"


def _fetch_rows(cursor, plan: EvalPlan, run_name: str, retries: int, sleep: Callable[[float], None]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    database, schema, agent = plan.agent_fqn.split(".")
    for attempt in range(retries + 1):
        cursor.execute(
            "SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(%s,%s,%s,'CORTEX AGENT',%s))",
            (database, schema, agent, run_name),
        )
        columns = [str(item[0]).lower() for item in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        if rows and any(row.get("metric_name") for row in rows):
            return rows
        if attempt < retries:
            sleep(1)
    return rows


def _agent_provenance(cursor, plan: EvalPlan) -> dict[str, Any]:
    cursor.execute(f"DESCRIBE AGENT {plan.agent_fqn}")
    columns = [str(item[0]).lower() for item in cursor.description]
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"Agent {plan.agent_fqn} does not exist")
    aliases: dict[str, Any] = {}
    if "aliases" in columns and row[columns.index("aliases")]:
        raw = row[columns.index("aliases")]
        aliases = json.loads(raw) if isinstance(raw, str) else dict(raw)
    default_version = aliases.get("DEFAULT")
    if not default_version:
        raise RuntimeError(f"Agent {plan.agent_fqn} has no resolvable DEFAULT version")
    return {"default_version": str(default_version), "aliases": aliases}


def _assert_agent_exists_with_default(cursor, plan: EvalPlan) -> dict[str, Any]:
    try:
        provenance = _agent_provenance(cursor, plan)
    except Exception as exc:
        raise RuntimeError(
            f"Evaluation requires existing Agent {plan.agent_fqn} with a resolvable DEFAULT version"
        ) from exc
    return provenance


def _default_connect(connection: str):
    try:
        import snowflake.connector
    except ImportError as exc:
        raise RuntimeError(
            "Evaluation execution requires the 'runtime' extra: pip install 'dbt-cortex-agent[runtime]'"
        ) from exc
    return snowflake.connector.connect(connection_name=connection)


def run_evaluation(
    config: Config,
    plan: EvalPlan,
    *,
    apply: bool,
    run_name: str | None = None,
    poll_attempts: int = 60,
    poll_interval: float = 30,
    transient_retries: int = 1,
    allowed_targets: list[str] | None = None,
    allowed_databases: list[str] | None = None,
    connect: Callable[[str], Any] = _default_connect,
    sleep: Callable[[float], None] = time.sleep,
) -> Path | None:
    if not apply:
        return None
    if not config.connection_explicit or not config.connection or not config.warehouse:
        raise ValueError("Evaluation apply requires explicit --connection and --warehouse")
    assert_apply_safety(config, allowed_targets or [], allowed_databases or [])
    if transient_retries < 0:
        raise ValueError("Transient retries must be non-negative")
    if config.database and identifier(config.database, "configured database") != plan.target_database:
        raise ValueError(
            f"Configured database {config.database!r} does not match dbt plan target database "
            f"{plan.target_database!r}"
        )
    if config.target and config.target != plan.target_name:
        raise ValueError(
            f"Configured target {config.target!r} does not match dbt plan target {plan.target_name!r}"
        )
    base_run = run_name or (
        f"{plan.agent_name}_{plan.suite_name}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    )
    conn = connect(config.connection)
    cursor = conn.cursor()
    try:
        cursor.execute(f"USE ROLE {plan.target_role}")
        cursor.execute(f"USE WAREHOUSE {identifier(plan.target_warehouse or config.warehouse, 'warehouse')}")
        cursor.execute(f"USE DATABASE {plan.target_database}")
        cursor.execute(f"USE SCHEMA {plan.target_schema}")
        initial_provenance = _assert_agent_exists_with_default(cursor, plan)
        validate_table(cursor, plan.table_fqn, plan.metric_names, plan.ordered_ground_truth_refs)
        final_run = base_run
        status = PollResult("FAILED", "evaluation was not started")
        pre_start: dict[str, Any] | None = None
        for retry in range(transient_retries + 1):
            final_run = base_run if retry == 0 else f"{base_run}-r{retry}"
            dataset_name = f"{final_run}_dataset"
            filename = plan.config_filename_template.replace("__RUN_NAME__", final_run)
            stage_path = _upload_config(cursor, plan, filename, render_eval_config(plan, dataset_name))
            pre_start = _assert_agent_exists_with_default(cursor, plan)
            if pre_start["default_version"] != initial_provenance["default_version"]:
                raise RuntimeError(
                    f"Agent {plan.agent_fqn} DEFAULT version changed before evaluation START"
                )
            cursor.execute(
                "CALL EXECUTE_AI_EVALUATION('START', OBJECT_CONSTRUCT('run_name', %s), %s)",
                (final_run, stage_path),
            )
            status = poll(
                cursor, final_run, stage_path, attempts=poll_attempts, interval=poll_interval, sleep=sleep
            )
            if status.succeeded or not is_retryable(status.details) or retry == transient_retries:
                break
        if not status.succeeded:
            raise RuntimeError(f"Evaluation {final_run} ended in {status.status}: {status.details}")
        rows = _fetch_rows(cursor, plan, final_run, retries=2, sleep=sleep)
        if not rows or not any(row.get("metric_name") for row in rows):
            raise RuntimeError(f"Evaluation {final_run} returned no scored metric rows")
        annotate_rows(cursor, plan.table_fqn, rows)
        post_completion = _assert_agent_exists_with_default(cursor, plan)
        if pre_start is None:
            raise RuntimeError("Evaluation provenance was not captured before START")
        provenance = {
            "agent_fqn": plan.agent_fqn,
            "plan_identity": plan.plan_identity,
            "evaluated_version": pre_start["default_version"],
            "pre_start": pre_start,
            "post_completion": post_completion,
            "default_version_changed": (
                pre_start["default_version"] != post_completion["default_version"]
            ),
        }
        candidate = build_candidate(
            plan=plan, run_name=final_run, rows=rows, provenance=provenance
        )
        return write_candidate(candidate, config.artifact_dir)
    finally:
        cursor.close()
        conn.close()