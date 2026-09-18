from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .config import Config
from .dbt_runner import CommandRunner, run_dbt_build
from .domain import (
    DurablePhaseError,
    LifecyclePhase,
    OperationOutcome,
    SnowflakeObjectName,
    is_controlled_operation_error,
)
from .identifiers import identifier
from .manifest import assert_resource_databases_allowed, select_agents
from .skills import build_upload_plan, upload_skills

DEPLOY_PHASE_PREFIX = "CORTEX_AGENT_DEPLOY_PHASE="


def _dbt_phases(output: str, outcome: OperationOutcome) -> OperationOutcome:
    known = {phase.value: phase for phase in LifecyclePhase}
    for line in output.splitlines():
        if DEPLOY_PHASE_PREFIX not in line:
            continue
        marker = line.split(DEPLOY_PHASE_PREFIX, 1)[1].strip()
        agent_fqn = None
        name = marker
        if marker.startswith("{"):
            try:
                payload = json.loads(marker)
                name = payload.get("phase")
                agent_fqn = str(SnowflakeObjectName.parse(payload.get("agent_fqn")))
            except (ValueError, TypeError):
                continue
        if (
            isinstance(name, str)
            and name in known
            and all(
                (item.phase, item.agent_fqn) != (known[name], agent_fqn) for item in outcome.phases
            )
        ):
            outcome = outcome.complete(known[name], agent_fqn=agent_fqn)
    return outcome


@dataclass(frozen=True)
class DeployPlan:
    agents: tuple[dict[str, str], ...]
    skill_uploads: tuple[Any, ...]
    dbt_selection: tuple[str, ...]
    resource_databases: tuple[str, ...]


def _dependency_databases(
    manifest: dict[str, Any], selected: list[dict[str, Any]]
) -> tuple[str, ...]:
    nodes = manifest.get("nodes")
    sources = manifest.get("sources")
    resources: dict[str, Any] = {
        **(nodes if isinstance(nodes, dict) else {}),
        **(sources if isinstance(sources, dict) else {}),
    }
    parent_map = manifest.get("parent_map")
    parent_map = parent_map if isinstance(parent_map, dict) else {}
    approved_ids = {agent["unique_id"] for agent in selected}
    if any(not isinstance(value, str) or not value for value in approved_ids):
        raise ValueError("Selected Agents must have manifest unique_id values")
    pending = list(approved_ids)
    visited: set[str] = set()
    databases: set[str] = set()
    while pending:
        unique_id = pending.pop()
        if unique_id in visited:
            continue
        visited.add(unique_id)
        resource = resources.get(unique_id)
        if isinstance(resource, dict):
            resource_config = resource.get("config", {})
            if (
                isinstance(resource_config, dict)
                and resource_config.get("materialized") == "cortex_agent"
                and unique_id not in approved_ids
            ):
                raise ValueError(
                    f"Unselected Agent ancestor {unique_id!r}; explicitly select every "
                    "Agent ancestor and review its skills/databases before deployment"
                )
        if isinstance(resource, dict) and resource.get("database"):
            databases.add(
                identifier(str(resource["database"]), f"database for dependency {unique_id}")
            )
        dependencies = resource.get("depends_on", {}) if isinstance(resource, dict) else {}
        declared_parents = dependencies.get("nodes", []) if isinstance(dependencies, dict) else []
        parents = parent_map.get(unique_id, declared_parents)
        if not isinstance(parents, list) or any(not isinstance(item, str) for item in parents):
            raise ValueError(
                f"dbt manifest parent_map entry for {unique_id!r} must be a list of IDs"
            )
        pending.extend(parents)
        if not isinstance(declared_parents, list) or any(
            not isinstance(item, str) for item in declared_parents
        ):
            raise ValueError(f"dbt dependency nodes for {unique_id!r} must be a list of IDs")
        pending.extend(declared_parents)
    return tuple(sorted(databases))


def build_deploy_plan(
    manifest: dict[str, Any], config: Config, agent_names: list[str] | None
) -> DeployPlan:
    selected = select_agents(manifest, agent_names)
    resource_databases = set(_dependency_databases(manifest, selected))
    agents = tuple(
        {
            "name": item["name"],
            "unique_id": item["unique_id"],
            "database": item["database"],
            "schema": item["schema"],
            "object_name": item["object_name"],
            "physical_fqn": item["physical_fqn"],
        }
        for item in selected
    )
    names = [item["name"] for item in selected]
    uploads = tuple(build_upload_plan(manifest, config.project_dir, names))
    resource_databases.update(upload.stage_fqn.split(".", 1)[0] for upload in uploads)
    return DeployPlan(
        agents=agents,
        skill_uploads=uploads,
        dbt_selection=tuple(f"+{name}" for name in names),
        resource_databases=tuple(sorted(resource_databases)),
    )


def validate_deploy_plan(
    plan: DeployPlan,
    config: Config,
    allowed_targets: list[str],
    allowed_databases: list[str],
) -> None:
    if not config.target or config.target not in allowed_targets:
        raise ValueError(
            f"Refusing deploy for target {config.target!r}; allowed targets: "
            f"{', '.join(allowed_targets) or 'none'}"
        )
    assert_resource_databases_allowed(plan.resource_databases, allowed_databases)


def apply_deploy_plan(
    plan: DeployPlan,
    config: Config,
    *,
    runner: CommandRunner | None = None,
) -> OperationOutcome:
    command_runner = runner or CommandRunner()
    outcome = OperationOutcome().complete(LifecyclePhase.PREFLIGHT)
    try:
        uploads = upload_skills(list(plan.skill_uploads), config, command_runner)
    except DurablePhaseError as exc:
        raise DurablePhaseError(
            f"Agent skill upload failed: {exc}",
            OperationOutcome((*outcome.phases, *exc.outcome.phases)),
        ) from exc
    except Exception as exc:
        if not is_controlled_operation_error(exc):
            raise
        raise DurablePhaseError(
            f"Agent skill upload failed: {exc}",
            outcome.fail(LifecyclePhase.SKILLS_UPLOADED, str(exc)),
        ) from exc
    outcome = OperationOutcome((*outcome.phases, *uploads.phases)).complete(
        LifecyclePhase.SKILLS_UPLOADED
    )
    result = run_dbt_build(
        config.dbt_executable,
        config.project_dir,
        config.target,
        plan.dbt_selection,
        command_runner,
        config.dbt_env,
        variables={
            "cortex_agent_expected_fqns": {
                agent["unique_id"]: agent["physical_fqn"] for agent in plan.agents
            }
        },
    )
    output = "\n".join(value for value in (result.stdout, result.stderr) if value)
    outcome = _dbt_phases(output, outcome)
    if result.returncode != 0:
        details = [value.strip() for value in (result.stdout, result.stderr) if value.strip()]
        detail = "\n".join(details) or "dbt build failed"
        message = (
            "Agent deployment failed after skill upload; dbt may have partially applied "
            f"selected resources: {detail}"
        )
        raise DurablePhaseError(
            message,
            outcome.fail(
                LifecyclePhase.VERIFIED,
                "dbt build failed; Agent reconciliation phase is indeterminate: " + detail,
            ),
        )
    return outcome.complete(LifecyclePhase.VERIFIED)
