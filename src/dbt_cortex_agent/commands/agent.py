from __future__ import annotations

import argparse
import json

from ..config import Config
from ..identifiers import identifier
from ..invoke import invoke_agent
from ..manifest import assert_config_database, physical_agent_name, select_agents
from ..skills import assert_apply_safety
from .common import add_allowlists, emit_json, fresh_manifest, require_explicit_connection


def register(subparsers: argparse._SubParsersAction, shared: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "agent",
        help="smoke a dbt-deployed Agent",
        description="Preview or invoke an Agent already deployed by dbt build.",
        epilog=(
            "Examples:\n"
            "  dbt-cortex-agent agent smoke --agent orders_assistant "
            "--question 'What was total revenue?' --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="agent_command", required=True)
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
    return _handle_smoke(args, config, manifest)