from __future__ import annotations

import argparse
import json

from ..config import Config
from ..deploy import deploy_agents, lifecycle_macro, render_agents
from ..identifiers import identifier, version
from ..invoke import invoke_agent
from ..manifest import assert_config_database, physical_agent_name, select_agents
from ..skills import assert_apply_safety
from .common import add_allowlists, emit_json, fresh_manifest, require_explicit_connection


def register(subparsers: argparse._SubParsersAction, shared: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "agent",
        help="run Agent lifecycle macros",
        description="Render or dry-run Agent lifecycle macros; mutations require explicit --apply.",
        epilog=(
            "Examples:\n"
            "  dbt-cortex-agent agent render --agent orders_assistant --json\n"
            "  dbt-cortex-agent agent deploy --agent orders_assistant --apply --connection dev"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="agent_command", required=True)
    render = commands.add_parser("render", parents=[shared], help="render Agent specifications")
    render.add_argument("--agent", action="append", dest="agents", help="logical Agent name; repeatable")
    render.set_defaults(handler=handle)

    deploy = commands.add_parser("deploy", parents=[shared], help="dry-run or deploy Agents [MUTATION with --apply]")
    deploy.add_argument("--agent", action="append", dest="agents", help="logical Agent name; repeatable")
    deploy.add_argument("--alias", help="alias assigned by the deploy macro")
    _add_apply(deploy)
    deploy.set_defaults(handler=handle)

    smoke = commands.add_parser(
        "smoke",
        parents=[shared],
        help="preview or invoke one Agent [RUNTIME with --apply]",
    )
    smoke.add_argument("--agent", required=True, help="logical Agent name")
    smoke.add_argument("--question", required=True, help="question sent to the Agent")
    smoke.add_argument("--expect-tool", help="exact tool name required in the response")
    smoke.add_argument("--agent-object", help="physical Agent override")
    smoke.add_argument("--endpoint", help="HTTPS Snowflake Agent endpoint override")
    smoke.add_argument("--apply", action="store_true", help="[RUNTIME] invoke the Agent; default is preview")
    add_allowlists(smoke)
    smoke.set_defaults(handler=handle)

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


def _nonblank(value: str | None, option: str) -> str:
    if value is None or not value.strip():
        raise ValueError(f"{option} must be nonblank")
    return value


def _handle_smoke(args: argparse.Namespace, config: Config, manifest: dict) -> int:
    logical_agent = _nonblank(args.agent, "--agent")
    question = _nonblank(args.question, "--question")
    expected_tool = (
        _nonblank(args.expect_tool, "--expect-tool") if args.expect_tool is not None else None
    )
    selected = select_agents(manifest, [logical_agent])[0]
    if args.agent_object is not None:
        agent_object = identifier(args.agent_object, "Agent object override")
    else:
        agent_object = physical_agent_name(selected, config.target)
    response = None
    passed = None
    if args.apply:
        require_explicit_connection(config, "Agent smoke")
        database = assert_config_database(manifest, config.database)
        assert_apply_safety(config, args.allow_target, args.allow_database)
        if not config.schema:
            raise ValueError("Agent smoke requires --schema or SNOWFLAKE_SCHEMA")
        response = invoke_agent(
            database,
            config.schema,
            agent_object,
            question,
            str(config.connection),
            args.endpoint,
        )
        passed = expected_tool is None or any(
            item.get("name") == expected_tool for item in response.get("tool_uses", [])
        )
        if not passed:
            raise RuntimeError(
                f"Agent smoke failed: expected tool {expected_tool!r} was not selected"
            )
    payload = {
        "command": "agent smoke",
        "applied": bool(args.apply),
        "agent": logical_agent,
        "agent_object": agent_object,
        "question": question,
        "expected_tool": expected_tool,
        "passed": passed,
        "response": response,
    }
    if args.json:
        emit_json(payload)
    elif args.apply:
        print(f"PASS {logical_agent} via {agent_object}")
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(f"[DRY RUN] would smoke {logical_agent} via {agent_object}: {question}")
    return 0


def handle(args: argparse.Namespace, config: Config) -> int:
    manifest = fresh_manifest(config, no_parse=args.no_parse)
    if args.agent_command == "smoke":
        return _handle_smoke(args, config, manifest)
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
        if args.agent_command == "grant":
            macro, arguments = "cortex_agent__grant_usage", {}
        elif args.agent_command == "promote":
            macro = "cortex_agent__promote_alias"
            arguments = {"from_alias": args.from_alias, "to_alias": args.to_alias}
        else:
            macro = "cortex_agent__rollback_alias"
            arguments = {"alias": args.alias, "to_version": args.to_version}
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
    if args.agent_command in {"render", "deploy"}:
        payload["renders"] = list(result.renders)
    if args.json:
        emit_json(payload)
    else:
        print(f"Processed Agents: {', '.join(result.agents) or 'none'}")
        for rendered in getattr(result, "renders", ()):
            artifact = (
                f"\nArtifact: {rendered['artifact']}" if rendered.get("artifact") else ""
            )
            print(
                f"Rendered {rendered['agent']} -> "
                f"{rendered['physical_agent']}{artifact}\n"
                f"{json.dumps(rendered['spec'], indent=2, sort_keys=True)}"
            )
    return 0