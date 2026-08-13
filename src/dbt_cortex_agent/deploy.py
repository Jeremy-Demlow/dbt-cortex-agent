from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .artifacts import contained_path
from .config import Config
from .dbt_runner import CommandRunner
from .manifest import assert_config_database, load_manifest, select_agents
from .skills import assert_apply_safety, build_upload_plan, upload_skills


@dataclass(frozen=True)
class LifecycleResult:
    agents: tuple[str, ...]
    commands: tuple[tuple[str, ...], ...]
    renders: tuple[dict[str, object], ...] = ()


RENDER_MARKER = "__DBT_CORTEX_AGENT_RENDER__="


def run_operation(
    config: Config,
    macro: str,
    arguments: dict,
    runner: CommandRunner | None = None,
    variables: dict | None = None,
) -> tuple[str, ...]:
    command, _ = _run_operation_result(config, macro, arguments, runner, variables)
    return command


def _run_operation_result(
    config: Config,
    macro: str,
    arguments: dict,
    runner: CommandRunner | None = None,
    variables: dict | None = None,
) -> tuple[tuple[str, ...], object]:
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
    command_runner = runner or CommandRunner()
    if config.dbt_env is None:
        result = command_runner.run(command, cwd=config.project_dir)
    else:
        result = command_runner.run(command, cwd=config.project_dir, env=config.dbt_env)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"dbt macro failed: {macro}")
    return tuple(command), result


def _parse_render_output(stdout: str, expected_agent: str) -> dict:
    marker_count = stdout.count(RENDER_MARKER)
    if marker_count != 1:
        raise ValueError(
            f"Expected exactly one {RENDER_MARKER[:-1]} marker for Agent "
            f"{expected_agent!r}; found {marker_count}"
        )
    marked = [
        line.split(RENDER_MARKER, 1)[1].strip()
        for line in stdout.splitlines()
        if RENDER_MARKER in line
    ]
    try:
        payload = json.loads(marked[0])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Malformed render marker JSON for Agent {expected_agent!r}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Render marker for Agent {expected_agent!r} must contain a JSON object")
    if payload.get("agent") != expected_agent:
        raise ValueError(f"Render marker Agent does not match requested Agent {expected_agent!r}")
    if payload.get("lifecycle_contract") != "single_agent":
        raise ValueError("Render marker lifecycle_contract must be 'single_agent'")
    for key in ("target", "physical_agent"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError(f"Render marker field {key!r} must be a non-empty string")
    if not isinstance(payload.get("spec"), dict):
        raise ValueError(f"Render marker spec for Agent {expected_agent!r} must be a JSON object")
    return payload


def _write_render_artifact(config: Config, payload: dict) -> Path:
    path = contained_path(
        config.artifact_dir,
        "renders",
        payload["target"],
        payload["agent"],
        "spec.json",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload["spec"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


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
    config: Config,
    agent_names: list[str] | None,
    runner: CommandRunner | None = None,
) -> LifecycleResult:
    _, agents = _selected(config, agent_names)
    command_runner = runner or CommandRunner()
    commands = []
    renders = []
    for agent in agents:
        if agent.get("resource_type") == "model":
            raise ValueError(
                f"Agent {agent['name']!r} is a cortex_agent model; use dbt build --select "
                f"{agent['name']} for render/deploy"
            )
        command, result = _run_operation_result(
            config,
            "cortex_agent__render_spec",
            {"agent_name": agent["name"]},
            command_runner,
        )
        payload = _parse_render_output(result.stdout, agent["name"])
        artifact = _write_render_artifact(config, payload)
        renders.append({**payload, "artifact": str(artifact)})
        commands.append(command)
    return LifecycleResult(
        tuple(agent["name"] for agent in agents), tuple(commands), tuple(renders)
    )


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
    renders = []
    for agent in agents:
        if agent.get("resource_type") == "model":
            raise ValueError(
                f"Agent {agent['name']!r} is a cortex_agent model; use dbt build --select "
                f"{agent['name']} for deployment"
            )
        arguments = {
            "agent_name": agent["name"],
            "dry_run": not apply,
        }
        if alias:
            arguments["alias"] = alias
        command, result = _run_operation_result(
            config,
            "cortex_agent__deploy",
            arguments,
            command_runner,
            _allowlist_variables(allowed_targets, allowed_databases) if apply else None,
        )
        commands.append(command)
        renders.append(_parse_render_output(result.stdout, agent["name"]))
    return LifecycleResult(tuple(selected_names), tuple(commands), tuple(renders))


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