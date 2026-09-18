from __future__ import annotations

import argparse
import json

from ..artifacts import contained_path
from ..config import Config
from ..deployment import apply_deploy_plan, build_deploy_plan, validate_deploy_plan
from ..domain import AgentVersionSelector, DurablePhaseError
from ..identifiers import identifier
from ..invoke import AgentInvocationError, compact_agent_output, invoke_agent
from ..lifecycle import apply_route_plan, build_route_plan, drop_agent, read_version_state
from ..manifest import (
    assert_resource_databases_allowed,
    physical_agent_name,
    select_agents,
)
from ..scaffold import apply_scaffold_plan, build_scaffold_plan
from ..skills import assert_apply_safety
from .common import add_allowlists, emit_json, fresh_manifest, require_explicit_connection

RETAINED_ON_DROP = (
    "dbt source files",
    "Semantic Views",
    "Cortex Sense contexts",
    "Search services",
    "stages and skills",
    "MCP servers",
    "evaluation results",
    "candidates and baselines",
)


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
    scaffold = commands.add_parser(
        "scaffold",
        parents=[shared],
        help="preview or create a generic Agent model [LOCAL MUTATION with --apply]",
    )
    scaffold.add_argument("--agent", required=True, help="new lowercase logical Agent name")
    scaffold.add_argument(
        "--semantic-view-model",
        help="optional dbt Semantic View model used by a generated Analyst tool",
    )
    scaffold.add_argument(
        "--with-eval",
        action="store_true",
        help="also create an editable evaluation model and suite",
    )
    scaffold.add_argument(
        "--apply",
        action="store_true",
        help="[LOCAL MUTATION] create planned files; default is preview",
    )
    scaffold.set_defaults(handler=handle_scaffold)
    versions = commands.add_parser(
        "versions", parents=[shared], help="inspect immutable Agent versions [READ ONLY]"
    )
    versions.add_argument("--agent", required=True, help="logical Agent name")
    versions.set_defaults(handler=handle)
    for action in ("promote", "rollback"):
        route = commands.add_parser(
            action,
            parents=[shared],
            help=f"preview or {action} Agent routing [MUTATION with --apply]",
        )
        route.add_argument("--agent", required=True, help="logical Agent name")
        version_option = "--version" if action == "promote" else "--to-version"
        route.add_argument(version_option, dest="to_version", required=True)
        route.add_argument("--alias", required=True, help="serving alias to move")
        route.add_argument(
            "--set-default",
            action="store_true",
            help="also route unversioned calls to this version",
        )
        route.add_argument(
            "--apply", action="store_true", help="[MUTATION] apply routing; default is preview"
        )
        add_allowlists(route)
        route.set_defaults(handler=handle)
    drop = commands.add_parser(
        "drop", parents=[shared], help="preview or retire one Agent [DESTRUCTIVE with --apply]"
    )
    drop.add_argument("--agent", required=True, help="logical Agent name")
    drop.add_argument("--confirm-agent", help="exact physical Agent FQN required for apply")
    drop.add_argument(
        "--apply", action="store_true", help="[DESTRUCTIVE] retire Agent; default is preview"
    )
    add_allowlists(drop)
    drop.set_defaults(handler=handle)
    deploy = commands.add_parser(
        "deploy",
        parents=[shared],
        help="preview or deploy Agents through dbt [MUTATION with --apply]",
    )
    deploy.add_argument(
        "--agent",
        action="append",
        dest="agents",
        required=True,
        help="logical Agent name; repeatable",
    )
    deploy.add_argument(
        "--apply",
        action="store_true",
        help="[MUTATION] upload skills and run dbt build; default is preview",
    )
    add_allowlists(deploy)
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
    smoke.add_argument(
        "--version",
        dest="agent_version",
        help="committed version, alias, or DEFAULT/FIRST/LAST/LIVE selector",
    )
    smoke.add_argument("--endpoint", help="HTTPS Snowflake Agent endpoint override")
    smoke.add_argument(
        "--raw-events",
        help="explicit artifact filename under target/dbt_cortex_agent/raw-events",
    )
    smoke.add_argument(
        "--apply", action="store_true", help="[RUNTIME] invoke the Agent; default is preview"
    )
    add_allowlists(smoke)
    smoke.set_defaults(handler=handle)


def _nonblank(value: str | None, option: str) -> str:
    if value is None or not value.strip():
        raise ValueError(f"{option} must be nonblank")
    return value


def handle_scaffold(args: argparse.Namespace, config: Config) -> int:
    plan = build_scaffold_plan(
        config,
        args.agent,
        args.semantic_view_model,
        with_eval=bool(args.with_eval),
    )
    if args.apply:
        apply_scaffold_plan(plan)
    payload = plan.to_dict(config.project_dir, applied=bool(args.apply))
    if args.json:
        emit_json(payload)
    else:
        prefix = "CREATED" if args.apply else "[DRY RUN]"
        print(f"{prefix} Agent scaffold for {plan.agent}")
        for action in plan.actions:
            path = action.path.relative_to(config.project_dir).as_posix()
            print(f"  {action.action}: {path}")
    return 0


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
    requested_version = None
    runtime_object = agent_object
    if args.agent_version is not None:
        requested_version = AgentVersionSelector.parse(args.agent_version).value
        runtime_object = f"{agent_object}!{requested_version}"
    response = None
    raw_event_path = None
    passed = None
    if args.apply:
        require_explicit_connection(config, "Agent smoke")
        assert_apply_safety(config, args.allow_target, args.allow_database)
        assert_resource_databases_allowed({selected["database"]}, args.allow_database)
        if config.database and config.database.upper() != selected["database"]:
            raise ValueError(
                f"Configured database {config.database!r} does not match selected Agent database "
                f"{selected['database']!r}"
            )
        if config.schema and config.schema.upper() != selected["schema"]:
            raise ValueError(
                f"Configured schema {config.schema!r} does not match selected Agent schema "
                f"{selected['schema']!r}"
            )
        if args.raw_events:
            raw_event_path = contained_path(config.artifact_dir, "raw-events", args.raw_events)
            if raw_event_path.exists():
                raise FileExistsError(f"Raw Agent event artifact already exists: {raw_event_path}")
        try:
            response = invoke_agent(
                selected["database"],
                selected["schema"],
                runtime_object,
                question,
                str(config.connection),
                args.endpoint,
                role=config.role,
                raw_event_path=raw_event_path,
            )
        except AgentInvocationError as exc:
            response = exc.result
            raw_event_path = exc.raw_event_path
            passed = False
        else:
            passed = expected_tool is None or any(
                item.get("name") == expected_tool for item in response.get("tool_uses", [])
            )
    payload = {
        "command": "agent smoke",
        "applied": bool(args.apply),
        "agent": logical_agent,
        "agent_object": agent_object,
        "runtime_object": runtime_object,
        "requested_version": requested_version,
        "question": question,
        "expected_tool": expected_tool,
        "passed": passed,
        "response": response,
        "raw_event_artifact": str(raw_event_path) if raw_event_path else None,
    }
    if args.json:
        emit_json(payload)
    elif args.apply:
        status = "PASS" if passed else "FAIL"
        print(f"{status} {logical_agent} via {agent_object}")
        print(compact_agent_output(response or {}))
    else:
        print(f"[DRY RUN] would smoke {logical_agent} via {agent_object}: {question}")
    return 2 if args.apply and passed is False else 0


def _emit(args: argparse.Namespace, payload: dict) -> None:
    if args.json:
        emit_json(payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


def _handle_deploy(args: argparse.Namespace, config: Config, manifest: dict) -> int:
    plan = build_deploy_plan(manifest, config, args.agents)
    validate_deploy_plan(plan, config, args.allow_target, args.allow_database)
    outcome = None
    if args.apply:
        require_explicit_connection(config, "Agent deploy")
        try:
            outcome = apply_deploy_plan(plan, config)
        except DurablePhaseError as exc:
            _emit(
                args,
                {
                    "command": "agent deploy",
                    "applied": True,
                    "status": "partial_failure",
                    "error": str(exc),
                    "target": config.target,
                    "agents": list(plan.agents),
                    "phases": exc.outcome.to_dict(),
                },
            )
            return 2
    payload = {
        "command": "agent deploy",
        "applied": bool(args.apply),
        "target": config.target,
        "agents": list(plan.agents),
        "skill_uploads": [
            {
                "stage_path": item.stage_path,
                "local_dir": str(item.local_dir),
                "skills": list(item.skill_names),
                "agents": list(item.agent_names),
            }
            for item in plan.skill_uploads
        ],
        "dbt_selection": list(plan.dbt_selection),
        "resource_databases": list(plan.resource_databases),
        "phases": outcome.to_dict() if outcome else [],
    }
    if args.json:
        emit_json(payload)
    elif args.apply:
        print("PASS deployed " + ", ".join(item["physical_fqn"] for item in plan.agents))
    else:
        print("[DRY RUN] " + json.dumps(payload, indent=2))
    return 0


def _handle_versions(args: argparse.Namespace, config: Config, manifest: dict) -> int:
    logical_agent = _nonblank(args.agent, "--agent")
    selected = select_agents(manifest, [logical_agent])[0]
    require_explicit_connection(config, "Agent versions")
    state = read_version_state(config, logical_agent)
    _emit(
        args,
        {
            "command": "agent versions",
            "agent": logical_agent,
            "agent_fqn": selected["physical_fqn"],
            "state": state,
        },
    )
    return 0


def _handle_route(args: argparse.Namespace, config: Config, manifest: dict) -> int:
    logical_agent = _nonblank(args.agent, "--agent")
    selected = select_agents(manifest, [logical_agent])[0]
    route_plan = build_route_plan(
        args.agent_command,
        selected,
        args.to_version,
        args.alias,
        bool(args.set_default),
    )
    result = None
    if args.apply:
        require_explicit_connection(config, f"Agent {args.agent_command}")
        assert_apply_safety(config, args.allow_target, args.allow_database)
        assert_resource_databases_allowed({selected["database"]}, args.allow_database)
        result = apply_route_plan(config, route_plan)
    _emit(args, route_plan.to_dict(applied=bool(args.apply), result=result))
    return 2 if result and result.get("status") == "partial_failure" else 0


def _handle_drop(args: argparse.Namespace, config: Config, manifest: dict) -> int:
    logical_agent = _nonblank(args.agent, "--agent")
    selected = select_agents(manifest, [logical_agent])[0]
    physical_fqn = selected["physical_fqn"]
    result = None
    if args.apply:
        require_explicit_connection(config, "Agent drop")
        if args.confirm_agent != physical_fqn:
            raise ValueError(f"Agent drop requires --confirm-agent {physical_fqn}")
        assert_apply_safety(config, args.allow_target, args.allow_database)
        assert_resource_databases_allowed({selected["database"]}, args.allow_database)
        result = drop_agent(config, logical_agent, physical_fqn)
    _emit(
        args,
        {
            "command": "agent drop",
            "applied": bool(args.apply),
            "agent": logical_agent,
            "agent_fqn": physical_fqn,
            "retained": list(RETAINED_ON_DROP),
            "result": result,
        },
    )
    return 2 if result and result.get("status") == "partial_failure" else 0


def handle(args: argparse.Namespace, config: Config) -> int:
    manifest = fresh_manifest(config, no_parse=args.no_parse)
    handlers = {
        "deploy": _handle_deploy,
        "versions": _handle_versions,
        "promote": _handle_route,
        "rollback": _handle_route,
        "drop": _handle_drop,
    }
    handler = handlers.get(args.agent_command, _handle_smoke)
    return handler(args, config, manifest)
