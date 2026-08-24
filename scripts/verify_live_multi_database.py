#!/usr/bin/env python3
"""Run or preview the exact-wheel protected multi-database package proof."""

from __future__ import annotations

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

    @property
    def databases(self) -> tuple[str, str, str]:
        return (self.database_a, self.database_b, self.eval_database)


def _identifier(value: str, label: str) -> str:
    normalized = value.upper()
    if not _ID.fullmatch(normalized):
        raise ValueError(f"{label} must be an unquoted Snowflake identifier")
    return normalized


def _run(command: list[str], *, cwd: Path, env: dict[str, str], apply: bool) -> str:
    if not apply:
        print("[DRY RUN] " + " ".join(command))
        return ""
    result = subprocess.run(
        command, cwd=cwd, env=env, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"Command failed with exit {result.returncode}: {' '.join(command)}: {detail}"
        )
    return result.stdout


def commands(config: LiveConfig, python: Path) -> list[list[str]]:
    cli = python.parent / "dbt-cortex-agent"
    dbt = python.parent / "dbt"
    allow = [item for database in config.databases for item in ("--allow-database", database)]
    common = [
        "--project-dir", str(config.project_dir), "--target", config.target,
        "--connection", config.connection, "--database", config.database_a,
        "--warehouse", config.warehouse,
    ]
    selection = "+live_orders_a +live_orders_b live_orders_a_core"
    return [
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", str(config.wheel),
         "dbt-core~=1.11.0", "dbt-snowflake==1.11.4"],
        [str(dbt), "deps", "--project-dir", str(config.project_dir), "--profiles-dir", str(config.project_dir)],
        [str(dbt), "parse", "--project-dir", str(config.project_dir), "--profiles-dir", str(config.project_dir),
         "--target", config.target, "--no-partial-parse"],
        [str(cli), "doctor", *common, "--json"],
        [str(cli), "manifest", "validate", *common, "--json"],
        [str(cli), "skill", "plan", *common, "--json"],
        [str(dbt), "build", "--project-dir", str(config.project_dir), "--profiles-dir", str(config.project_dir),
         "--target", config.target, "--select", selection],
        [str(cli), "agent", "smoke", *common, "--schema", "AGENTS", "--agent", "live_orders_a",
         "--question", "What was total order revenue?", "--allow-target", config.target, *allow, "--apply"],
        [str(cli), "agent", "smoke", *common, "--database", config.database_b, "--schema", "AGENTS",
         "--agent", "live_orders_b", "--question", "What was total order revenue?",
         "--allow-target", config.target, *allow, "--apply"],
        [str(cli), "eval", "run", *common, "--agent", "live_orders_a", "--suite", "core", "--json"],
        [str(dbt), "build", "--project-dir", str(config.project_dir), "--profiles-dir", str(config.project_dir),
         "--target", config.target, "--select", selection],
    ]


def cleanup_commands(config: LiveConfig) -> list[list[str]]:
    statements = (
        f"DROP AGENT IF EXISTS {config.database_a}.AGENTS.SHARED_ASSISTANT",
        f"DROP AGENT IF EXISTS {config.database_b}.AGENTS.SHARED_ASSISTANT",
        f"DROP TABLE IF EXISTS {config.eval_database}.EVAL.LIVE_ORDERS_A_CORE",
        f"DROP SEMANTIC VIEW IF EXISTS {config.database_a}.SEMANTIC.SEM_ORDERS_LIVE",
    )
    return [
        ["snow", "sql", "--connection", config.connection, "--query", statement]
        for statement in statements
    ]


def _agent_state(config: LiveConfig, database: str, env: dict[str, str]) -> dict:
    fqn = f"{database}.AGENTS.SHARED_ASSISTANT"
    versions_raw = _run(
        ["snow", "sql", "--connection", config.connection, "--format", "json",
         "--query", f"SHOW VERSIONS IN AGENT {fqn}"],
        cwd=config.project_dir, env=env, apply=True,
    )
    aliases_raw = _run(
        ["snow", "sql", "--connection", config.connection, "--format", "json",
         "--query", f"DESCRIBE AGENT {fqn}"],
        cwd=config.project_dir, env=env, apply=True,
    )
    versions = json.loads(versions_raw or "[]")
    description = json.loads(aliases_raw or "[]")
    committed = []
    for row in versions:
        if not isinstance(row, dict):
            continue
        normalized = {str(key).lower(): value for key, value in row.items()}
        if normalized.get("name"):
            committed.append(str(normalized["name"]))
    committed.sort()
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


def _cleanup(config: LiveConfig, env: dict[str, str], apply: bool) -> None:
    failures = []
    for command in cleanup_commands(config):
        try:
            _run(command, cwd=config.project_dir, env=env, apply=apply)
        except RuntimeError as exc:
            failures.append(str(exc))
    if failures:
        raise RuntimeError("Cleanup failed: " + "; ".join(failures))


def run(
    config: LiveConfig, *, apply: bool, cleanup: bool, cleanup_only: bool = False
) -> Path:
    for label, value in (
        ("database A", config.database_a), ("database B", config.database_b),
        ("evaluation database", config.eval_database), ("role", config.role),
        ("warehouse", config.warehouse),
    ):
        _identifier(value, label)
    if len(set(config.databases)) != 3:
        raise ValueError("Live proof requires three distinct databases")
    if not cleanup_only and not config.wheel.is_file():
        raise FileNotFoundError(config.wheel)
    venv = config.artifact_dir / "venv"
    python = venv / "bin/python"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{python.parent}{os.pathsep}{env.get('PATH', '')}",
            "DBT_TARGET": config.target,
            "SNOWFLAKE_DATABASE": config.database_a,
            "SNOWFLAKE_ROLE": config.role,
            "SNOWFLAKE_WAREHOUSE": config.warehouse,
            "CORTEX_AGENT_LIVE_DATABASE_A": config.database_a,
            "CORTEX_AGENT_LIVE_DATABASE_B": config.database_b,
            "CORTEX_AGENT_LIVE_DATABASE_EVAL": config.eval_database,
        }
    )
    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    if cleanup_only:
        _cleanup(config, env, apply)
        return config.artifact_dir / "live-attestation.json"
    if apply:
        _run([sys.executable, "-m", "venv", str(venv)], cwd=config.project_dir, env=env, apply=True)
    first_state: list[dict] = []
    second_state: list[dict] = []
    proof_error: Exception | None = None
    try:
        planned = commands(config, python)
        for index, command in enumerate(planned):
            _run(command, cwd=config.project_dir, env=env, apply=apply)
            if apply and index == 6:
                first_state = [
                    _agent_state(config, database, env)
                    for database in (config.database_a, config.database_b)
                ]
            if apply and index == len(planned) - 1:
                second_state = [
                    _agent_state(config, database, env)
                    for database in (config.database_a, config.database_b)
                ]
        if apply and first_state != second_state:
            raise RuntimeError("No-change reconciliation changed Agent versions or aliases")
    except Exception as exc:
        proof_error = exc
        raise
    finally:
        if cleanup:
            try:
                _cleanup(config, env, apply)
            except RuntimeError:
                if proof_error is None:
                    raise
    attestation = {
        "schema_version": 1,
        "status": "completed" if apply else "planned",
        "wheel_sha256": hashlib.sha256(config.wheel.read_bytes()).hexdigest(),
        "target": config.target,
        "agents": second_state or [
            {"agent_fqn": f"{config.database_a}.AGENTS.SHARED_ASSISTANT"},
            {"agent_fqn": f"{config.database_b}.AGENTS.SHARED_ASSISTANT"},
        ],
        "eval_database": config.eval_database,
        "paid_evaluation": False,
        "cleanup_requested": cleanup,
        "dbt_package_source": "release checkout matching the wheel build",
    }
    output = config.artifact_dir / "live-attestation.json"
    output.write_text(json.dumps(attestation, indent=2) + "\n", encoding="utf-8")
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
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--cleanup-only", action="store_true")
    args = parser.parse_args()
    output = run(
        LiveConfig(
            project_dir=Path(args.project_dir).resolve(), wheel=Path(args.wheel).resolve(),
            connection=args.connection, target=args.target,
            database_a=args.database_a, database_b=args.database_b,
            eval_database=args.eval_database, role=args.role, warehouse=args.warehouse,
            artifact_dir=Path(args.artifact_dir).resolve(),
        ),
        apply=args.apply,
        cleanup=args.cleanup,
        cleanup_only=args.cleanup_only,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())