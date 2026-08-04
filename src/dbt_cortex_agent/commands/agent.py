from __future__ import annotations

import argparse

from ..config import Config
from ..deploy import deploy_agents, lifecycle_macro, render_agents
from ..identifiers import identifier, version
from ..manifest import assert_config_database
from .common import add_allowlists, emit_json, fresh_manifest, require_explicit_connection


def register(subparsers: argparse._SubParsersAction, shared: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "agent",
        help="run canonical Agent lifecycle macros",
        description="Render or dry-run Agent lifecycle macros; mutations require explicit --apply.",
        epilog=(
            "Examples:\n"
            "  dbt-cortex-agent agent render --agent orders_assistant --json\n"
            "  dbt-cortex-agent agent deploy --agent orders_assistant --apply --connection dev"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="agent_command", required=True)
    render = commands.add_parser("render", parents=[shared], help="render canonical Agent specifications")
    render.add_argument("--agent", action="append", dest="agents", help="logical Agent name; repeatable")
    render.set_defaults(handler=handle)

    deploy = commands.add_parser("deploy", parents=[shared], help="dry-run or deploy Agents [MUTATION with --apply]")
    deploy.add_argument("--agent", action="append", dest="agents", help="logical Agent name; repeatable")
    deploy.add_argument("--alias", help="alias assigned by the deploy macro")
    _add_apply(deploy)
    deploy.set_defaults(handler=handle)

    grant = commands.add_parser("grant", parents=[shared], help="dry-run or grant Agent usage [MUTATION with --apply]")
    grant.add_argument("--agent", action="append", dest="agents", help="logical Agent name; repeatable")
    _add_apply(grant)
    grant.set_defaults(handler=handle)

    promote = commands.add_parser("promote", parents=[shared], help="dry-run or move an alias [MUTATION with --apply]")
    promote.add_argument("--agent", action="append", dest="agents", help="logical Agent name; repeatable")
    promote.add_argument("--from-alias", required=True, help="source alias")
    promote.add_argument("--to-alias", required=True, help="target alias")
    _add_apply(promote)
    promote.set_defaults(handler=handle)

    rollback = commands.add_parser("rollback", parents=[shared], help="dry-run or roll back an alias [MUTATION with --apply]")
    rollback.add_argument("--agent", action="append", dest="agents", help="logical Agent name; repeatable")
    rollback.add_argument("--alias", required=True, help="alias to move")
    rollback.add_argument("--to-version", required=True, help="target VERSION$N")
    _add_apply(rollback)
    rollback.set_defaults(handler=handle)


def _add_apply(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--apply", action="store_true", help="[MUTATION] execute lifecycle changes; default is dry-run")
    add_allowlists(parser)


def handle(args: argparse.Namespace, config: Config) -> int:
    manifest = fresh_manifest(config, no_parse=args.no_parse)
    if args.agent_command == "deploy" and args.alias:
        args.alias = identifier(args.alias, "alias")
    elif args.agent_command == "promote":
        args.from_alias = identifier(args.from_alias, "source alias")
        args.to_alias = identifier(args.to_alias, "target alias")
    elif args.agent_command == "rollback":
        args.alias = identifier(args.alias, "alias")
        args.to_version = version(args.to_version)
    apply = bool(getattr(args, "apply", False))
    if args.agent_command != "render" and apply:
        require_explicit_connection(config, f"Agent {args.agent_command}")
        assert_config_database(manifest, config.database)
    if args.agent_command == "render":
        result = render_agents(config, args.agents)
    elif args.agent_command == "deploy":
        result = deploy_agents(
            config,
            args.agents,
            apply=apply,
            allowed_targets=args.allow_target,
            allowed_databases=args.allow_database,
            alias=args.alias,
        )
    else:
        macro_by_command = {
            "grant": ("cortex_agent__grant_usage", {}),
            "promote": ("cortex_agent__promote_alias", {"from_alias": args.from_alias, "to_alias": args.to_alias}),
            "rollback": ("cortex_agent__rollback_alias", {"alias": args.alias, "to_version": args.to_version}),
        }
        macro, arguments = macro_by_command[args.agent_command]
        result = lifecycle_macro(
            config,
            args.agents,
            macro,
            arguments,
            apply=apply,
            allowed_targets=args.allow_target,
            allowed_databases=args.allow_database,
        )
    payload = {"command": f"agent {args.agent_command}", "applied": apply, "agents": list(result.agents)}
    if args.json:
        emit_json(payload)
    else:
        print(f"Processed Agents: {', '.join(result.agents) or 'none'}")
    return 0