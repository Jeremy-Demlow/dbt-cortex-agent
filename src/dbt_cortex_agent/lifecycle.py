from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .config import Config
from .dbt_runner import CommandRunner, run_dbt_operation
from .domain import (
    AgentVersionSelector,
    SnowflakeObjectName,
    VersionKind,
    is_controlled_operation_error,
)
from .identifiers import identifier

VERSION_STATE_PREFIX = "CORTEX_AGENT_VERSION_STATE="
ROUTE_RESULT_PREFIX = "CORTEX_AGENT_ROUTE_RESULT="
DEFAULT_ROUTE_RESULT_PREFIX = "CORTEX_AGENT_DEFAULT_ROUTE_RESULT="
DROP_RESULT_PREFIX = "CORTEX_AGENT_DROP_RESULT="
RESERVED_ROUTE_ALIASES = {"DEFAULT", "FIRST", "LAST", "LIVE"}


@dataclass(frozen=True)
class RoutePlan:
    action: str
    agent: str
    agent_fqn: SnowflakeObjectName
    to_version: str
    alias: str
    set_default: bool

    def to_dict(self, *, applied: bool, result: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "command": f"agent {self.action}",
            "applied": applied,
            "agent": self.agent,
            "agent_fqn": str(self.agent_fqn),
            "to_version": self.to_version,
            "alias": self.alias,
            "set_default": self.set_default,
            "result": result,
        }


def _marked_json(stdout: str, prefix: str) -> dict[str, Any]:
    values = [line.split(prefix, 1)[1].strip() for line in stdout.splitlines() if prefix in line]
    if len(values) != 1:
        raise RuntimeError(
            f"Expected exactly one {prefix.rstrip('=')} payload, found {len(values)}"
        )
    value = json.loads(values[0])
    if not isinstance(value, dict):
        raise RuntimeError(f"{prefix.rstrip('=')} payload must be an object")
    return value


def _operation(config: Config, macro: str, arguments: dict[str, object], runner=None):
    result = run_dbt_operation(
        config.dbt_executable,
        config.project_dir,
        config.target,
        macro,
        arguments,
        runner or CommandRunner(),
        config.dbt_env,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"{macro} failed"
        raise RuntimeError(detail)
    return result.stdout


def build_route_plan(
    action: str,
    agent: dict[str, Any],
    to_version: str,
    alias: str,
    set_default: bool,
) -> RoutePlan:
    if action not in {"promote", "rollback"}:
        raise ValueError(f"Unsupported Agent routing action: {action}")
    selector = AgentVersionSelector.parse(to_version, "target Agent version")
    if selector.kind is not VersionKind.COMMITTED:
        raise ValueError("target Agent version must be an immutable VERSION$N")
    safe_alias = identifier(alias, "Agent alias")
    if safe_alias in RESERVED_ROUTE_ALIASES:
        raise ValueError(f"Agent alias {safe_alias!r} is reserved for Snowflake routing")
    return RoutePlan(
        action,
        str(agent["name"]),
        SnowflakeObjectName.parse(str(agent["physical_fqn"]), "Agent FQN"),
        selector.value,
        safe_alias,
        set_default,
    )


def read_version_state(config: Config, agent_name: str, *, runner=None) -> dict[str, Any]:
    stdout = _operation(
        config,
        "dbt_cortex_agent.cortex_agent__version_state_for_model",
        {"agent_name": agent_name},
        runner,
    )
    return _marked_json(stdout, VERSION_STATE_PREFIX)


def _inspect_state(
    config: Config, agent_name: str, runner
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return read_version_state(config, agent_name, runner=runner), None
    except Exception as exc:
        if not is_controlled_operation_error(exc):
            raise
        return None, str(exc)


def apply_route_plan(config: Config, plan: RoutePlan, *, runner=None) -> dict[str, Any]:
    planned_state = read_version_state(config, plan.agent, runner=runner)
    expected_alias_version = planned_state.get("aliases", {}).get(plan.alias, "")
    expected_default_version = planned_state.get("default_version") or ""
    try:
        alias_stdout = _operation(
            config,
            "dbt_cortex_agent.cortex_agent__route_alias",
            {
                "agent_name": plan.agent,
                "to_version": plan.to_version,
                "alias": plan.alias,
                "expected_alias_version": expected_alias_version,
            },
            runner,
        )
        alias_result = _marked_json(alias_stdout, ROUTE_RESULT_PREFIX)
    except Exception as exc:
        if not is_controlled_operation_error(exc):
            raise
        observed_state, inspection_error = _inspect_state(config, plan.agent, runner)
        return {
            "agent_fqn": str(plan.agent_fqn),
            "to_version": plan.to_version,
            "alias": plan.alias,
            "set_default": plan.set_default,
            "status": "partial_failure",
            "error": str(exc),
            "after": observed_state,
            "phases": [
                {
                    "phase": "alias",
                    "status": "failed",
                    "error": str(exc),
                    "state": observed_state,
                    "inspection_error": inspection_error,
                }
            ],
        }
    phases = [{"phase": "alias", "status": "completed", "state": alias_result.get("after")}]
    if not plan.set_default:
        return {**alias_result, "status": "completed", "phases": phases}

    try:
        default_stdout = _operation(
            config,
            "dbt_cortex_agent.cortex_agent__route_default",
            {
                "agent_name": plan.agent,
                "to_version": plan.to_version,
                "expected_default_version": expected_default_version,
            },
            runner,
        )
        default_result = _marked_json(default_stdout, DEFAULT_ROUTE_RESULT_PREFIX)
    except Exception as exc:
        if not is_controlled_operation_error(exc):
            raise
        observed_state, inspection_error = _inspect_state(config, plan.agent, runner)
        phases.append(
            {
                "phase": "default",
                "status": "failed",
                "error": str(exc),
                "state": observed_state,
                "inspection_error": inspection_error,
            }
        )
        return {
            **alias_result,
            "status": "partial_failure",
            "error": str(exc),
            "after": observed_state,
            "phases": phases,
        }

    phases.append({"phase": "default", "status": "completed", "state": default_result.get("after")})
    return {
        **alias_result,
        "status": "completed",
        "after": default_result.get("after"),
        "phases": phases,
    }


def drop_agent(config: Config, agent_name: str, *, runner=None) -> dict[str, Any]:
    stdout = _operation(
        config,
        "dbt_cortex_agent.cortex_agent__drop",
        {"agent_name": agent_name},
        runner,
    )
    return _marked_json(stdout, DROP_RESULT_PREFIX)
