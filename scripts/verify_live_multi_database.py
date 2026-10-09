#!/usr/bin/env python3
"""Run or preview the exact-wheel protected multi-database package proof."""

from __future__ import annotations

# Evidence: TC-022-11 TC-025-06 TC-025-07 TC-025-13 TC-025-14 TC-026-08 TC-026-10
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


class UnknownServerState(RuntimeError):
    """A local timeout requires reconciliation before any cleanup or retry."""


@dataclass(frozen=True)
class LiveConfig:
    project_dir: Path
    wheel: Path
    connection: str
    target: str
    database_a: str
    database_b: str
    eval_database: str
    role: str
    warehouse: str
    artifact_dir: Path
    expected_organization: str = "SFSENORTHAMERICA"
    expected_account: str = "DEMO_JDEMLOW"

    @property
    def databases(self) -> tuple[str, str, str]:
        return (self.database_a, self.database_b, self.eval_database)


def _identifier(value: str, label: str) -> str:
    normalized = value.upper()
    if not _ID.fullmatch(normalized):
        raise ValueError(f"{label} must be an unquoted Snowflake identifier")
    return normalized


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    apply: bool,
    capture: bool = True,
) -> str:
    if not apply:
        print("[DRY RUN] " + " ".join(command))
        return ""
    try:
        result = subprocess.run(
            command, cwd=cwd, env=env, text=True, capture_output=capture, check=False, timeout=600
        )
    except subprocess.TimeoutExpired as exc:
        raise UnknownServerState(
            "Local command timeout; server state unknown; reconcile before retry"
        ) from exc
    if result.returncode != 0:
        details = [
            value.strip()
            for value in (result.stdout, result.stderr)
            if isinstance(value, str) and value.strip()
        ]
        detail = "\n".join(details)
        raise RuntimeError(
            f"Command failed with exit {result.returncode}: {' '.join(command)}: {detail}"
        )
    return result.stdout or ""


def commands(config: LiveConfig, python: Path) -> list[list[str]]:
    cli = python.parent / "dbt-cortex-agent"
    dbt = python.parent / "dbt"
    allow = [item for database in config.databases for item in ("--allow-database", database)]
    common = [
        "--project-dir",
        str(config.project_dir),
        "--target",
        config.target,
        "--connection",
        config.connection,
        "--database",
        config.database_a,
        "--role",
        config.role,
        "--warehouse",
        config.warehouse,
    ]
    return [
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            str(config.wheel),
            "dbt-core==1.11.11",
            "dbt-snowflake==1.11.4",
        ],
        [
            str(dbt),
            "deps",
            "--project-dir",
            str(config.project_dir),
            "--profiles-dir",
            str(config.project_dir),
        ],
        [str(cli), "manifest", "validate", *common, "--agent", "live_orders_a", "--json"],
        [
            str(cli),
            "agent",
            "deploy",
            *common,
            "--agent",
            "live_orders_a",
            "--agent",
            "live_orders_b",
            "--allow-target",
            config.target,
            *allow,
            "--apply",
            "--json",
        ],
        [
            str(cli),
            "agent",
            "smoke",
            *common,
            "--schema",
            "AGENTS",
            "--agent",
            "live_orders_a",
            "--question",
            "What was total order revenue?",
            "--allow-target",
            config.target,
            *allow,
            "--apply",
        ],
        [
            str(cli),
            "agent",
            "smoke",
            *common,
            "--database",
            config.database_b,
            "--schema",
            "AGENTS",
            "--agent",
            "live_orders_b",
            "--question",
            "What was total order revenue?",
            "--allow-target",
            config.target,
            *allow,
            "--apply",
        ],
        [
            str(cli),
            "eval",
            "verify",
            *common,
            "--agent",
            "live_orders_a",
            "--suite",
            "core",
            "--allow-target",
            config.target,
            *allow,
            "--json",
        ],
        [
            str(cli),
            "agent",
            "deploy",
            *common,
            "--agent",
            "live_orders_a",
            "--agent",
            "live_orders_b",
            "--allow-target",
            config.target,
            *allow,
            "--apply",
            "--json",
        ],
    ]


def lifecycle_commands(config: LiveConfig, python: Path) -> list[list[str]]:
    cli = python.parent / "dbt-cortex-agent"
    common = [
        "--project-dir",
        str(config.project_dir),
        "--target",
        config.target,
        "--connection",
        config.connection,
        "--database",
        config.database_a,
        "--role",
        config.role,
        "--warehouse",
        config.warehouse,
        "--agent",
        "live_orders_a",
        "--allow-target",
        config.target,
        "--allow-database",
        config.database_a,
    ]
    smoke = [
        str(cli),
        "agent",
        "smoke",
        *common,
        "--question",
        "What was total order revenue?",
        "--schema",
        "AGENTS",
        "--apply",
    ]
    return [
        [
            str(cli),
            "agent",
            "promote",
            *common,
            "--version",
            "VERSION$1",
            "--alias",
            "production",
            "--set-default",
            "--apply",
            "--json",
        ],
        [str(cli), "agent", "deploy", *common, "--apply", "--json"],
        [*smoke, "--version", "VERSION$2"],
        [
            str(cli),
            "agent",
            "promote",
            *common,
            "--version",
            "VERSION$2",
            "--alias",
            "production",
            "--set-default",
            "--apply",
            "--json",
        ],
        [
            str(cli),
            "agent",
            "rollback",
            *common,
            "--to-version",
            "VERSION$1",
            "--alias",
            "production",
            "--set-default",
            "--apply",
            "--json",
        ],
        [*smoke, "--version", "VERSION$1"],
        [str(cli), "agent", "deploy", *common, "--apply", "--json"],
        [
            str(cli),
            "agent",
            "promote",
            *common,
            "--version",
            "VERSION$2",
            "--alias",
            "production",
            "--set-default",
            "--apply",
            "--json",
        ],
        [
            str(cli),
            "agent",
            "versions",
            "--project-dir",
            str(config.project_dir),
            "--target",
            config.target,
            "--connection",
            config.connection,
            "--database",
            config.database_a,
            "--role",
            config.role,
            "--warehouse",
            config.warehouse,
            "--agent",
            "live_orders_a",
            "--json",
        ],
    ]


def guarded_drop_commands(config: LiveConfig, python: Path) -> list[list[str]]:
    cli = python.parent / "dbt-cortex-agent"
    result = []
    for agent, database in (
        ("live_orders_a", config.database_a),
        ("live_orders_b", config.database_b),
    ):
        fqn = f"{database}.AGENTS.SHARED_ASSISTANT"
        result.append(
            [
                str(cli),
                "agent",
                "drop",
                "--project-dir",
                str(config.project_dir),
                "--target",
                config.target,
                "--connection",
                config.connection,
                "--database",
                database,
                "--role",
                config.role,
                "--warehouse",
                config.warehouse,
                "--agent",
                agent,
                "--confirm-agent",
                fqn,
                "--allow-target",
                config.target,
                "--allow-database",
                database,
                "--apply",
                "--json",
            ]
        )
    return result


def cleanup_commands(config: LiveConfig) -> list[list[str]]:
    statements = (
        f"DROP AGENT IF EXISTS {config.database_a}.AGENTS.SHARED_ASSISTANT",
        f"DROP AGENT IF EXISTS {config.database_b}.AGENTS.SHARED_ASSISTANT",
        f"DROP TABLE IF EXISTS {config.eval_database}.EVAL.LIVE_ORDERS_A_CORE",
        f"DROP SEMANTIC VIEW IF EXISTS {config.database_a}.SEMANTIC.SEM_ORDERS_LIVE",
    )
    return [_snow_command(config, statement) for statement in statements]


def _snow_command(config: LiveConfig, sql: str) -> list[str]:
    return [
        "snow",
        "sql",
        "--connection",
        config.connection,
        "--role",
        config.role,
        "--warehouse",
        config.warehouse,
        "--database",
        config.database_a,
        "--format",
        "json",
        "--query",
        sql,
    ]


def _rows(config: LiveConfig, sql: str, env: dict[str, str]) -> list[dict]:
    raw = _run(_snow_command(config, sql), cwd=config.project_dir, env=env, apply=True)
    rows = json.loads(raw)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("Snowflake inspection did not return an object-row array")
    return [{str(key).upper(): value for key, value in row.items()} for row in rows]


def _verify_identity(config: LiveConfig, env: dict[str, str]) -> None:
    rows = _rows(
        config,
        "SELECT CURRENT_ORGANIZATION_NAME() AS ORGANIZATION_NAME, "
        "CURRENT_ACCOUNT_NAME() AS ACCOUNT_NAME, CURRENT_ROLE() AS ROLE_NAME, "
        "CURRENT_DATABASE() AS DATABASE_NAME, CURRENT_WAREHOUSE() AS WAREHOUSE_NAME",
        env,
    )
    expected = {
        "ORGANIZATION_NAME": config.expected_organization,
        "ACCOUNT_NAME": config.expected_account,
        "ROLE_NAME": config.role,
        "DATABASE_NAME": config.database_a,
        "WAREHOUSE_NAME": config.warehouse,
    }
    if len(rows) != 1 or any(
        str(rows[0].get(key, "")).upper() != value.upper() for key, value in expected.items()
    ):
        raise RuntimeError("Live proof session identity mismatch; no cleanup authorized")


def _proof_inventory(config: LiveConfig, env: dict[str, str]) -> list[str]:
    inspections = [
        ("AGENTS", database, "AGENTS", "SHARED_ASSISTANT")
        for database in (config.database_a, config.database_b)
    ] + [
        ("SEMANTIC VIEWS", config.database_a, "SEMANTIC", "SEM_ORDERS_LIVE"),
        ("TABLES", config.eval_database, "EVAL", "LIVE_ORDERS_A_CORE"),
        ("TABLES", config.eval_database, "EVAL", "LIVE_ORDERS_A_CORE__DBT_TMP"),
        ("TABLES", config.eval_database, "EVAL", "LIVE_ORDERS_A_CORE__DBT_BACKUP"),
    ]
    found = []
    for kind, database, schema, name in inspections:
        rows = _rows(config, f"SHOW {kind} LIKE '{name}' IN SCHEMA {database}.{schema}", env)
        if any(str(row.get("NAME", "")).upper() == name for row in rows):
            found.append(f"{database}.{schema}.{name}")
    return found


def _preflight(config: LiveConfig, env: dict[str, str]) -> None:
    _verify_identity(config, env)
    if _proof_inventory(config, env):
        raise RuntimeError("Reserved proof objects already exist; refusing mutation or cleanup")
    tables = _rows(
        config, f"SHOW TABLES LIKE 'ORDERS' IN SCHEMA {config.database_a}.ANALYTICS", env
    )
    if any(str(row.get("NAME", "")).upper() == "ORDERS" for row in tables):
        rows = _rows(
            config,
            f"SELECT ORDER_ID, ORDER_DATE, REGION, REVENUE "
            f"FROM {config.database_a}.ANALYTICS.ORDERS ORDER BY ORDER_ID LIMIT 4",
            env,
        )
        expected = [
            ("1001", "2026-01-05", "North", 120.50),
            ("1002", "2026-01-12", "South", 75.00),
            ("1003", "2026-02-03", "North", 210.25),
        ]
        observed = [
            (
                str(row.get("ORDER_ID")),
                str(row.get("ORDER_DATE")),
                row.get("REGION"),
                float(row.get("REVENUE", 0)),
            )
            for row in rows
        ]
        if observed != expected:
            raise RuntimeError("Existing proof seed differs from reviewed synthetic input")


def _agent_state(config: LiveConfig, database: str, env: dict[str, str]) -> dict:
    fqn = f"{database}.AGENTS.SHARED_ASSISTANT"
    versions = _rows(config, f"SHOW VERSIONS IN AGENT {fqn}", env)
    description = _rows(config, f"DESCRIBE AGENT {fqn}", env)
    committed = []
    for row in versions:
        if not isinstance(row, dict):
            continue
        normalized = {str(key).lower(): value for key, value in row.items()}
        name = str(normalized.get("name", ""))
        if re.fullmatch(r"VERSION\$[1-9][0-9]*", name):
            committed.append(name)
    committed.sort(key=lambda value: int(value.split("$")[1]))
    aliases = None
    for row in description:
        if not isinstance(row, dict):
            continue
        normalized = {str(key).lower(): value for key, value in row.items()}
        value = normalized.get("aliases")
        if value:
            aliases = json.loads(value) if isinstance(value, str) else value
    if not committed or not isinstance(aliases, dict) or not aliases.get("DEFAULT"):
        raise RuntimeError(f"Agent state is incomplete for {fqn}")
    return {"agent_fqn": fqn, "versions": committed, "aliases": aliases}


def _assert_route_state(state: dict, versions: list[str], routed: str) -> None:
    if state.get("versions") != versions:
        raise RuntimeError("Lifecycle committed-version postcondition failed")
    aliases = state.get("aliases", {})
    if aliases.get("DEFAULT") != routed or aliases.get("PRODUCTION") != routed:
        raise RuntimeError("Lifecycle DEFAULT/PRODUCTION routing postcondition failed")


def _assert_lifecycle_state(state: dict) -> None:
    if state["versions"] != ["VERSION$1", "VERSION$2"]:
        raise RuntimeError(f"Expected exactly VERSION$1 and VERSION$2, got {state['versions']}")
    aliases = state["aliases"]
    if aliases.get("DEFAULT") != "VERSION$2" or aliases.get("PRODUCTION") != "VERSION$2":
        raise RuntimeError(f"Roll-forward routing postcondition failed: {aliases}")


def _cleanup(config: LiveConfig, env: dict[str, str], apply: bool) -> None:
    failures = []
    for command in cleanup_commands(config):
        try:
            _run(command, cwd=config.project_dir, env=env, apply=apply, capture=False)
        except UnknownServerState:
            raise
        except (RuntimeError, OSError) as exc:
            failures.append(str(exc))
    if failures:
        raise RuntimeError("Cleanup failed: " + "; ".join(failures))


def _write_attestation(output: Path, attestation: dict) -> None:
    proof_status = attestation["proof_status"]
    cleanup_status = attestation["cleanup_status"]
    failed = "failed" in (proof_status, cleanup_status) or attestation.get("server_state_unknown")
    attestation["status"] = "failed" if failed else proof_status
    output.write_text(json.dumps(attestation, indent=2) + "\n", encoding="utf-8")


def _record_cleanup(
    config: LiveConfig, env: dict[str, str], apply: bool, attestation: dict
) -> None:
    attestation["cleanup_requested"] = True
    if apply and attestation.get("server_state_unknown"):
        attestation["cleanup_status"] = "not_authorized"
        return
    attestation["cleanup_status"] = "planned"
    attestation.pop("cleanup_error_type", None)
    try:
        if apply:
            if not attestation.get("cleanup_authorized"):
                attestation["cleanup_status"] = "not_authorized"
                return
            _verify_identity(config, env)
        _cleanup(config, env, apply)
        if apply and _proof_inventory(config, env):
            raise RuntimeError("Proof objects remain after cleanup")
    except Exception as exc:
        attestation["cleanup_status"] = "failed"
        attestation["cleanup_error_type"] = type(exc).__name__
        if isinstance(exc, UnknownServerState):
            attestation["server_state_unknown"] = True
        raise
    else:
        if apply:
            attestation["cleanup_status"] = "completed"


def _prior_attestation(output: Path, expected: dict) -> dict:
    prior = json.loads(output.read_text(encoding="utf-8"))
    if not isinstance(prior, dict):
        raise ValueError("Existing live attestation must be an object")
    for key in ("schema_version", "target", "eval_database", "paid_evaluation", "execution_scope"):
        if prior.get(key) != expected[key]:
            raise ValueError(f"Existing live attestation has mismatched {key}")
    if (
        expected["wheel_sha256"] is not None
        and prior.get("wheel_sha256") != expected["wheel_sha256"]
    ):
        raise ValueError("Existing live attestation has mismatched wheel_sha256")
    agents = prior.get("agents")
    if (
        not isinstance(agents, list)
        or len(agents) != 2
        or any(not isinstance(agent, dict) for agent in agents)
    ):
        raise ValueError("Existing live attestation must retain both Agent identities")
    if [agent.get("agent_fqn") for agent in agents] != [
        agent["agent_fqn"] for agent in expected["agents"]
    ]:
        raise ValueError("Existing live attestation has mismatched Agent identities")
    if prior.get("proof_status") not in {"planned", "not_started", "completed", "failed"}:
        raise ValueError("Existing live attestation has no valid proof_status")
    if prior.get("cleanup_status") not in {
        "not_requested",
        "not_authorized",
        "planned",
        "completed",
        "failed",
    }:
        raise ValueError("Existing live attestation has no valid cleanup_status")
    return prior


def run(  # noqa: C901
    config: LiveConfig, *, apply: bool, cleanup: bool, cleanup_only: bool = False
) -> Path:
    for label, value in (
        ("database A", config.database_a),
        ("database B", config.database_b),
        ("evaluation database", config.eval_database),
        ("role", config.role),
        ("warehouse", config.warehouse),
        ("expected organization", config.expected_organization),
        ("expected account", config.expected_account),
    ):
        _identifier(value, label)
    if len({database.upper() for database in config.databases}) != 3:
        raise ValueError("Live proof requires three distinct databases")
    if not cleanup_only and not config.wheel.is_file():
        raise FileNotFoundError(config.wheel)
    venv = config.artifact_dir / "venv"
    python = venv / "bin/python"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{python.parent}{os.pathsep}{env.get('PATH', '')}",
            "DBT_EXECUTABLE": str(python.parent / "dbt"),
            "DBT_TARGET": config.target,
            "SNOWFLAKE_DATABASE": config.database_a,
            "SNOWFLAKE_ROLE": config.role,
            "SNOWFLAKE_WAREHOUSE": config.warehouse,
            "CORTEX_AGENT_LIVE_DATABASE_A": config.database_a,
            "CORTEX_AGENT_LIVE_DATABASE_B": config.database_b,
            "CORTEX_AGENT_LIVE_DATABASE_EVAL": config.eval_database,
            "CORTEX_AGENT_LIVE_SPEC_REVISION": "v1",
        }
    )
    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    output = config.artifact_dir / "live-attestation.json"
    if not cleanup_only and output.exists():
        raise ValueError("Proof evidence already exists; choose a new artifact directory")
    attestation = {
        "schema_version": 1,
        "proof_status": "not_started" if cleanup_only else "planned",
        "wheel_sha256": (
            hashlib.sha256(config.wheel.read_bytes()).hexdigest()
            if config.wheel.is_file()
            else None
        ),
        "target": config.target,
        "agents": [
            {"agent_fqn": f"{config.database_a}.AGENTS.SHARED_ASSISTANT"},
            {"agent_fqn": f"{config.database_b}.AGENTS.SHARED_ASSISTANT"},
        ],
        "eval_database": config.eval_database,
        "paid_evaluation": False,
        "cleanup_requested": cleanup or cleanup_only,
        "cleanup_status": "not_requested",
        "cleanup_authorized": False,
        "execution_scope": {
            "organization": config.expected_organization,
            "account": config.expected_account,
            "role": config.role,
            "warehouse": config.warehouse,
            "database": config.database_a,
        },
        "guarded_retirement": False,
        "dbt_package_source": "release checkout matching the wheel build",
        "reconciliation": {"before": [], "after": []},
        "default_pin_regression": {},
    }
    if cleanup_only:
        if output.exists():
            attestation = _prior_attestation(output, attestation)
            if not apply:
                _cleanup(config, env, apply=False)
                return output
        try:
            _record_cleanup(config, env, apply, attestation)
        finally:
            _write_attestation(output, attestation)
        return output
    first_state: list[dict] = []
    second_state: list[dict] = []
    attestation["reconciliation"] = {"before": first_state, "after": second_state}
    proof_error: Exception | None = None
    cleanup_error: Exception | None = None
    try:
        if apply:
            _preflight(config, env)
            attestation["cleanup_authorized"] = True
            _write_attestation(output, attestation)
            _run(
                [sys.executable, "-m", "venv", "--clear", str(venv)],
                cwd=config.project_dir,
                env=env,
                apply=True,
            )
        planned = commands(config, python)
        for index, command in enumerate(planned):
            _run(command, cwd=config.project_dir, env=env, apply=apply, capture=False)
            if apply and index in (3, len(planned) - 1):
                snapshot = first_state if index == 3 else second_state
                for position, database in enumerate((config.database_a, config.database_b)):
                    state = _agent_state(config, database, env)
                    snapshot.append(state)
                    attestation["agents"][position] = state
        if apply and first_state != second_state:
            raise RuntimeError("No-change reconciliation changed Agent versions or aliases")
        lifecycle_env = {**env, "CORTEX_AGENT_LIVE_SPEC_REVISION": "v2"}
        for index, command in enumerate(lifecycle_commands(config, python)):
            phase_env = env if index == 0 else lifecycle_env
            _run(command, cwd=config.project_dir, env=phase_env, apply=apply, capture=False)
            if apply and index in (0, 1, 3, 4, 6, 7):
                state = _agent_state(config, config.database_a, phase_env)
                versions = ["VERSION$1"] if index == 0 else ["VERSION$1", "VERSION$2"]
                routed = "VERSION$1" if index in (0, 1, 4, 6) else "VERSION$2"
                label = {
                    0: "pinned",
                    1: "after_candidate_commit",
                    3: "promoted",
                    4: "rolled_back",
                    6: "no_change",
                    7: "rolled_forward",
                }[index]
                attestation["default_pin_regression"][label] = state
                attestation["agents"][0] = state
                _write_attestation(output, attestation)
                _assert_route_state(state, versions, routed)
        if apply:
            lifecycle_state = _agent_state(config, config.database_a, lifecycle_env)
            attestation["agents"][0] = lifecycle_state
            _assert_lifecycle_state(lifecycle_state)
            for command in guarded_drop_commands(config, python):
                _run(command, cwd=config.project_dir, env=lifecycle_env, apply=True, capture=False)
            attestation["guarded_retirement"] = True
            attestation["proof_status"] = "completed"
    except Exception as exc:
        proof_error = exc
        attestation["proof_status"] = "failed"
        attestation["proof_error_type"] = type(exc).__name__
        if isinstance(exc, UnknownServerState):
            attestation["server_state_unknown"] = True
    finally:
        if cleanup:
            try:
                _record_cleanup(config, env, apply, attestation)
            except Exception as exc:
                cleanup_error = exc
        _write_attestation(output, attestation)
    if proof_error is not None:
        raise proof_error
    if cleanup_error is not None:
        raise cleanup_error
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", default="integration_tests")
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--connection", default="live-ci")
    parser.add_argument("--target", default="sandbox")
    parser.add_argument("--database-a", required=True)
    parser.add_argument("--database-b", required=True)
    parser.add_argument("--eval-database", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--warehouse", required=True)
    parser.add_argument("--expected-organization", default="SFSENORTHAMERICA")
    parser.add_argument("--expected-account", default="DEMO_JDEMLOW")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--cleanup-only", action="store_true")
    args = parser.parse_args()
    output = run(
        LiveConfig(
            project_dir=Path(args.project_dir).resolve(),
            wheel=Path(args.wheel).resolve(),
            connection=args.connection,
            target=args.target,
            database_a=args.database_a,
            database_b=args.database_b,
            eval_database=args.eval_database,
            role=args.role,
            warehouse=args.warehouse,
            artifact_dir=Path(args.artifact_dir).resolve(),
            expected_organization=args.expected_organization,
            expected_account=args.expected_account,
        ),
        apply=args.apply,
        cleanup=args.cleanup,
        cleanup_only=args.cleanup_only,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
