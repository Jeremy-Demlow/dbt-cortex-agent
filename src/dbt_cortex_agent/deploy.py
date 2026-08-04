from __future__ import annotations

import json
from dataclasses import dataclass

from .config import Config
from .dbt_runner import CommandRunner
from .manifest import assert_config_database, load_manifest, select_agents
from .skills import assert_apply_safety, build_upload_plan, upload_skills


@dataclass(frozen=True)
class LifecycleResult:
    agents: tuple[str, ...]
    commands: tuple[tuple[str, ...], ...]


def run_operation(
    config: Config,
    macro: str,
    arguments: dict,
    runner: CommandRunner | None = None,
    variables: dict | None = None,
) -> tuple[str, ...]:
    command = [
        config.dbt_executable,
        "run-operation",
        macro,
        "--args",
        json.dumps(arguments, separators=(",", ":"), sort_keys=True),
        "--project-dir",
        str(config.project_dir),
    ]
    if config.target:
        command.extend(["--target", config.target])
    if variables:
        command.extend(
            ["--vars", json.dumps(variables, separators=(",", ":"), sort_keys=True)]
        )
    result = (runner or CommandRunner()).run(command, cwd=config.project_dir)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"dbt macro failed: {macro}")
    return tuple(command)


def _allowlist_variables(
    allowed_targets: list[str], allowed_databases: list[str]
) -> dict[str, list[str]]:
    return {
        "cortex_agent_allowed_targets": allowed_targets,
        "cortex_agent_allowed_databases": allowed_databases,
    }


def validate_deploy_context(
    config: Config,
    allowed_targets: list[str],
    allowed_databases: list[str],
    runner: CommandRunner | None = None,
) -> tuple[str, ...]:
    assert_apply_safety(config, allowed_targets, allowed_databases)
    return run_operation(
        config,
        "cortex_agent__validate_deploy_context",
        {},
        runner,
        _allowlist_variables(allowed_targets, allowed_databases),
    )


def _selected(config: Config, agent_names: list[str] | None):
    manifest = load_manifest(config.manifest)
    return manifest, select_agents(manifest, agent_names)


def render_agents(
    config: Config, agent_names: list[str] | None, runner: CommandRunner | None = None
) -> LifecycleResult:
    _, agents = _selected(config, agent_names)
    commands = [
        run_operation(
            config,
            "cortex_agent__render_spec",
            {"agent_name": agent["name"], "projection": "canonical"},
            runner,
        )
        for agent in agents
    ]
    return LifecycleResult(tuple(agent["name"] for agent in agents), tuple(commands))


def deploy_agents(
    config: Config,
    agent_names: list[str] | None,
    *,
    apply: bool,
    allowed_targets: list[str],
    allowed_databases: list[str],
    alias: str | None = None,
    runner: CommandRunner | None = None,
) -> LifecycleResult:
    command_runner = runner or CommandRunner()
    manifest, agents = _selected(config, agent_names)
    selected_names = [agent["name"] for agent in agents]
    plan = build_upload_plan(manifest, config.project_dir, selected_names)
    if apply:
        assert_config_database(manifest, config.database)
        validate_deploy_context(
            config, allowed_targets, allowed_databases, command_runner
        )
        upload_skills(plan, config, command_runner)
    commands = []
    for agent in agents:
        arguments = {
            "agent_name": agent["name"],
            "projection": "canonical",
            "dry_run": not apply,
        }
        if alias:
            arguments["alias"] = alias
        commands.append(
            run_operation(
                config,
                "cortex_agent__deploy",
                arguments,
                command_runner,
                _allowlist_variables(allowed_targets, allowed_databases) if apply else None,
            )
        )
    return LifecycleResult(tuple(selected_names), tuple(commands))


def lifecycle_macro(
    config: Config,
    agent_names: list[str] | None,
    macro: str,
    arguments: dict,
    *,
    apply: bool,
    allowed_targets: list[str],
    allowed_databases: list[str],
    runner: CommandRunner | None = None,
) -> LifecycleResult:
    manifest, agents = _selected(config, agent_names)
    if apply:
        assert_config_database(manifest, config.database)
        validate_deploy_context(config, allowed_targets, allowed_databases, runner)
    commands = []
    for agent in agents:
        macro_args = {"agent_name": agent["name"], **arguments, "dry_run": not apply}
        commands.append(
            run_operation(
                config,
                macro,
                macro_args,
                runner,
                _allowlist_variables(allowed_targets, allowed_databases) if apply else None,
            )
        )
    return LifecycleResult(tuple(agent["name"] for agent in agents), tuple(commands))