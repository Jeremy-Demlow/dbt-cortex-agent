from __future__ import annotations

import argparse
import json
from typing import Any

from ..config import Config
from ..dbt_runner import CommandRunner, run_dbt_parse
from ..manifest import load_manifest


def shared_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--project-dir", help="dbt project directory (default: current directory)")
    parser.add_argument("--manifest", help="manifest path relative to the project directory")
    parser.add_argument("--target", help="explicit dbt target name")
    parser.add_argument("--connection", help="explicit Snowflake connection name for runtime operations")
    parser.add_argument("--database", help="expected Snowflake target database")
    parser.add_argument("--schema", help="Snowflake Agent schema for runtime operations")
    parser.add_argument("--warehouse", help="Snowflake warehouse for paid evaluation")
    parser.add_argument("--artifact-dir", help="local evaluation artifact directory")
    parser.add_argument("--dbt-executable", help="dbt executable (default: dbt)")
    parser.add_argument("--snow-executable", help="Snow CLI executable (default: snow)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--no-parse",
        action="store_true",
        help="skip fresh dbt parse only for controlled test fixtures; unsafe for normal use",
    )
    return parser


def add_allowlists(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--allow-target", action="append", default=[], help="allow mutation on this dbt target; repeatable")
    parser.add_argument("--allow-database", action="append", default=[], help="allow mutation in this database; repeatable")


def fresh_manifest(
    config: Config, *, no_parse: bool, runner: CommandRunner | None = None
) -> dict[str, Any]:
    if not no_parse:
        result = run_dbt_parse(
            config.dbt_executable,
            config.project_dir,
            config.target,
            runner or CommandRunner(),
            config.dbt_env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip() or result.stdout.strip() or "dbt parse failed"
            )
    return load_manifest(config.manifest)


def require_explicit_connection(config: Config, operation: str) -> None:
    if not config.connection_explicit or not config.connection:
        raise ValueError(f"{operation} requires an explicitly supplied --connection")


def emit_json(value: Any) -> None:
    print(json.dumps(value, indent=2, default=str))