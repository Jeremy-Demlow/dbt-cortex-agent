from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Config
from .dbt_runner import CommandRunner, run_dbt_build
from .manifest import assert_resource_databases_allowed, select_agents
from .skills import build_upload_plan, upload_skills


@dataclass(frozen=True)
class DeployPlan:
    agents: tuple[dict[str, str], ...]
    skill_uploads: tuple[Any, ...]
    dbt_selection: tuple[str, ...]


def build_deploy_plan(
    manifest: dict[str, Any], config: Config, agent_names: list[str] | None
) -> DeployPlan:
    selected = select_agents(manifest, agent_names)
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
    return DeployPlan(
        agents=agents,
        skill_uploads=tuple(build_upload_plan(manifest, config.project_dir, names)),
        dbt_selection=tuple(f"+{name}" for name in names),
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
    databases = {item["database"] for item in plan.agents}
    databases.update(upload.stage_fqn.split(".", 1)[0] for upload in plan.skill_uploads)
    assert_resource_databases_allowed(databases, allowed_databases)


def apply_deploy_plan(
    plan: DeployPlan,
    config: Config,
    *,
    runner: CommandRunner | None = None,
) -> None:
    command_runner = runner or CommandRunner()
    upload_skills(list(plan.skill_uploads), config, command_runner)
    result = run_dbt_build(
        config.dbt_executable,
        config.project_dir,
        config.target,
        plan.dbt_selection,
        command_runner,
        config.dbt_env,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "dbt build failed"
        raise RuntimeError(
            "Agent deployment failed after skill upload; dbt may have partially applied "
            f"selected resources: {detail}"
        )