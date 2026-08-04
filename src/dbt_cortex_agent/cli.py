from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError

import yaml

from . import __version__
from .commands import agent, bootstrap, eval, manifest, skill
from .commands.common import shared_parser
from .config import resolve_config


EXIT_SUCCESS = 0
EXIT_DIAGNOSTIC_FAILURE = 1
EXIT_CONTROLLED_ERROR = 2
VALID_HANDLER_EXIT_CODES = {EXIT_SUCCESS, EXIT_DIAGNOSTIC_FAILURE}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dbt-cortex-agent",
        description="Manage manifest-owned Cortex Agents with dry-run-safe dbt and local workflows.",
        epilog=(
            "Examples:\n"
            "  dbt-cortex-agent doctor --project-dir . --json\n"
            "  dbt-cortex-agent agent deploy --agent orders_assistant\n"
            "  dbt-cortex-agent eval run --agent orders_assistant --suite core\n\n"
            "Mutation and paid commands are dry-run by default and label the required --apply option."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    shared = shared_parser()
    for domain in (bootstrap, manifest, skill, agent, eval):
        domain.register(subparsers, shared)
    return parser


def _is_controlled_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (FileNotFoundError, OSError, RuntimeError, ValueError, HTTPError, URLError, yaml.YAMLError),
    ) or exc.__class__.__module__.startswith("snowflake.connector")


def _emit_error(exc: Exception, json_output: bool) -> None:
    if json_output:
        print(json.dumps({"error": str(exc), "exit_code": EXIT_CONTROLLED_ERROR}), file=sys.stderr)
    else:
        print(f"error: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        exit_code = int(args.handler(args, resolve_config(args)))
        if exit_code not in VALID_HANDLER_EXIT_CODES:
            raise RuntimeError(f"Command handler returned unsupported exit code {exit_code}")
        return exit_code
    except Exception as exc:
        if not _is_controlled_error(exc):
            raise
        _emit_error(exc, bool(getattr(args, "json", False)))
        return EXIT_CONTROLLED_ERROR


if __name__ == "__main__":
    raise SystemExit(main())