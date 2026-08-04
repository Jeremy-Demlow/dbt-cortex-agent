from __future__ import annotations

import argparse

from ..config import Config
from ..doctor import run_doctor
from ..init import DEFAULT_REVISION, initialize
from .common import add_allowlists, emit_json, fresh_manifest


def register(subparsers: argparse._SubParsersAction, shared: argparse.ArgumentParser) -> None:
    init_parser = subparsers.add_parser(
        "init",
        parents=[shared],
        help="preview or apply dbt package bootstrap [MUTATION with --apply]",
        description="Preview dbt package bootstrap; writing files requires --apply.",
        epilog="Example: dbt-cortex-agent init --package-source <git-url> --json",
    )
    init_parser.add_argument("--package-source", help="Git URL for a new package declaration")
    init_parser.add_argument("--revision", default=DEFAULT_REVISION, help=f"immutable package revision (default: {DEFAULT_REVISION})")
    init_parser.add_argument("--agent-schema", help="set cortex_agent_schema when absent")
    init_parser.add_argument("--eval-schema", help="set cortex_eval_schema when absent")
    add_allowlists(init_parser)
    init_parser.add_argument("--apply", action="store_true", help="[MUTATION] write bootstrap changes; default is preview")
    init_parser.add_argument("--run-dbt-deps", action="store_true", help="[MUTATION] run dbt deps after --apply")
    init_parser.set_defaults(handler=handle_init)

    doctor_parser = subparsers.add_parser(
        "doctor",
        parents=[shared],
        help="run non-mutating project diagnostics",
        description="Run local project, executable, manifest, safety, and optional connection diagnostics.",
        epilog="Example: dbt-cortex-agent doctor --project-dir . --json",
    )
    doctor_parser.set_defaults(handler=handle_doctor)


def handle_init(args: argparse.Namespace, config: Config) -> int:
    result = initialize(
        config,
        apply=args.apply,
        run_deps=args.run_dbt_deps,
        package_source=args.package_source,
        revision=args.revision,
        target=args.target,
        allowed_targets=args.allow_target,
        allowed_databases=args.allow_database,
        agent_schema=args.agent_schema,
        eval_schema=args.eval_schema,
    )
    if args.json:
        emit_json(
            {
                "command": "init",
                "applied": bool(args.apply),
                "changed_files": [str(path) for path in result.changed_files],
                "messages": list(result.messages),
            }
        )
    else:
        for message in result.messages:
            print(message)
    return 0


def handle_doctor(args: argparse.Namespace, config: Config) -> int:
    fresh_manifest(config, no_parse=args.no_parse)
    diagnostics = run_doctor(config)
    failed = any(item.status == "FAIL" for item in diagnostics)
    if args.json:
        emit_json(
            {
                "command": "doctor",
                "passed": not failed,
                "diagnostics": [item.__dict__ for item in diagnostics],
            }
        )
    else:
        for item in diagnostics:
            print(f"[{item.status}] {item.name}: {item.detail}")
    return 1 if failed else 0