from __future__ import annotations

import argparse

from ..config import Config
from ..domain import DurablePhaseError, OperationOutcome
from ..identifiers import identifier
from ..invoke import smoke_skills
from ..manifest import (
    assert_resource_databases_allowed,
    physical_agent_name,
    select_agents,
    skill_declarations,
)
from ..skills import assert_apply_safety, build_upload_plan, upload_skills
from .common import add_allowlists, emit_json, fresh_manifest, require_explicit_connection


def register(subparsers: argparse._SubParsersAction, shared: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "skill",
        help="plan, upload, or smoke Agent skills",
        description="Plan skill files locally; upload and live smoke require explicit --apply.",
        epilog=(
            "Examples:\n"
            "  dbt-cortex-agent skill plan --agent orders_assistant --json\n"
            "  dbt-cortex-agent skill upload --agent orders_assistant --apply --connection dev"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="skill_command", required=True)
    for name in ("plan", "upload"):
        help_text = (
            "build a non-mutating upload plan"
            if name == "plan"
            else "preview or apply skill upload [MUTATION with --apply]"
        )
        command = commands.add_parser(name, parents=[shared], help=help_text)
        command.add_argument(
            "--agent", action="append", dest="agents", help="logical Agent name; repeatable"
        )
        if name == "upload":
            command.add_argument(
                "--apply", action="store_true", help="[MUTATION] upload files; default is preview"
            )
            add_allowlists(command)
        command.set_defaults(handler=handle)
    smoke = commands.add_parser(
        "smoke", parents=[shared], help="preview or run live skill smoke [RUNTIME with --apply]"
    )
    smoke.add_argument(
        "--agent", action="append", dest="agents", help="logical Agent name; repeatable"
    )
    smoke.add_argument(
        "--agent-object", help="physical Agent override for exactly one selected Agent"
    )
    smoke.add_argument("--endpoint", help="HTTPS Snowflake Agent endpoint override")
    smoke.add_argument(
        "--apply", action="store_true", help="[RUNTIME] invoke Agents; default is preview"
    )
    add_allowlists(smoke)
    smoke.set_defaults(handler=handle)


def _plan_payload(plan: list) -> list[dict]:
    return [
        {
            "stage_path": item.stage_path,
            "local_dir": str(item.local_dir),
            "skills": list(item.skill_names),
            "agents": list(item.agent_names),
        }
        for item in plan
    ]


def _handle_upload(args: argparse.Namespace, config: Config, manifest: dict) -> int:
    plan = build_upload_plan(manifest, config.project_dir, args.agents)
    applied = args.skill_command == "upload" and args.apply
    outcome = OperationOutcome()
    error = None
    if applied:
        require_explicit_connection(config, "Skill upload")
        assert_apply_safety(config, args.allow_target, args.allow_database)
        assert_resource_databases_allowed(
            {item.stage_fqn.split(".", 1)[0] for item in plan}, args.allow_database
        )
        try:
            outcome = upload_skills(plan, config)
        except DurablePhaseError as exc:
            outcome = exc.outcome
            error = str(exc)
    payload = {
        "command": f"skill {args.skill_command}",
        "applied": applied,
        "uploads": _plan_payload(plan),
        "phases": outcome.to_dict(),
    }
    if error:
        payload.update(status="partial_failure", error=error)
    if args.json:
        emit_json(payload)
    elif error:
        print(error)
        for phase in outcome.to_dict():
            print(f"{phase['stage_path']}: completed={phase['completed']}")
    else:
        for item in plan:
            print(
                f"{item.stage_path} <- {item.local_dir} "
                f"(skills={','.join(item.skill_names)}; agents={','.join(item.agent_names)})"
            )
    return 2 if error else 0


def handle(args: argparse.Namespace, config: Config) -> int:
    manifest = fresh_manifest(config, no_parse=args.no_parse)
    if args.skill_command in {"plan", "upload"}:
        return _handle_upload(args, config, manifest)
    selected = select_agents(manifest, args.agents)
    selected_names = [item["name"] for item in selected]
    declarations = skill_declarations(manifest, config.project_dir, selected_names)
    if args.agent_object and len(selected) != 1:
        raise ValueError("--agent-object may be used only when exactly one Agent is selected")
    physical_agents = {
        agent["name"]: {
            "database": agent["database"],
            "schema": agent["schema"],
            "object_name": (
                identifier(args.agent_object, "Agent object override")
                if args.agent_object
                else physical_agent_name(agent, config.target)
            ),
        }
        for agent in selected
    }
    planned = [
        {
            "skill": skill.skill_name,
            "agent": ".".join(physical_agents[skill.agent_name].values()),
        }
        for skill in declarations
    ]
    verified: list[str] = []
    if args.apply:
        require_explicit_connection(config, "Skill smoke")
        assert_apply_safety(config, args.allow_target, args.allow_database)
        assert_resource_databases_allowed(
            {identity["database"] for identity in physical_agents.values()},
            args.allow_database,
        )
        verified = smoke_skills(
            declarations,
            agent_names=physical_agents,
            connection=str(config.connection),
            endpoint=args.endpoint,
            role=config.role,
        )
    if args.json:
        emit_json(
            {
                "command": "skill smoke",
                "applied": bool(args.apply),
                "planned": planned,
                "verified": verified,
            }
        )
    elif args.apply:
        for skill_name in verified:
            print(f"PASS {skill_name}: server_skill selected")
    else:
        for item in planned:
            print(f"[DRY RUN] would smoke {item['skill']} via {item['agent']}")
    return 0
