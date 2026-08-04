from __future__ import annotations

import argparse

from ..config import Config
from ..manifest import select_agents
from .common import emit_json, fresh_manifest


def register(subparsers: argparse._SubParsersAction, shared: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "manifest",
        help="validate resolved dbt metadata",
        description="Inspect freshly parsed manifest-owned Agent metadata.",
        epilog="Example: dbt-cortex-agent manifest validate --agent orders_assistant --json",
    )
    commands = parser.add_subparsers(dest="manifest_command", required=True)
    validate = commands.add_parser(
        "validate", parents=[shared], help="validate manifest and selected Agents"
    )
    validate.add_argument("--agent", action="append", dest="agents", help="logical Agent name; repeatable")
    validate.set_defaults(handler=handle_validate)


def handle_validate(args: argparse.Namespace, config: Config) -> int:
    manifest = fresh_manifest(config, no_parse=args.no_parse)
    agents = [item["name"] for item in select_agents(manifest, args.agents)]
    result = {"manifest": str(config.manifest), "agents": agents}
    if args.json:
        emit_json(result)
    else:
        print(f"Manifest: {config.manifest}")
        print(f"Agents: {', '.join(agents) or 'none'}")
    return 0