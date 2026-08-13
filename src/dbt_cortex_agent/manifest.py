from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .identifiers import fqn, identifier, stage_path


SUPPORTED_MANIFEST_SCHEMA_VERSIONS = {"v12"}


@dataclass(frozen=True)
class SkillDeclaration:
    agent_name: str
    skill_name: str
    source_type: str
    stage_path: str
    local_dir: Path


@dataclass(frozen=True)
class EvalDeclaration:
    model_name: str
    table_fqn: str
    meta: dict[str, Any]


def target_database(manifest: dict[str, Any]) -> str:
    project_name = (manifest.get("metadata") or {}).get("project_name")
    nodes = [
        node
        for node in (manifest.get("nodes") or {}).values()
        if isinstance(node, dict)
        and node.get("database")
        and node.get("resource_type", "model") == "model"
        and (not project_name or node.get("package_name", project_name) == project_name)
    ]
    databases = {
        identifier(node["database"], "dbt-resolved target database")
        for node in nodes
    }
    if len(databases) != 1:
        found = ", ".join(sorted(databases)) or "none"
        raise ValueError(
            "Expected exactly one dbt-resolved target database in manifest nodes; "
            f"found: {found}"
        )
    return next(iter(databases))


def assert_config_database(manifest: dict[str, Any], database: str | None) -> str:
    if not database:
        raise ValueError("Operation requires explicit --database or SNOWFLAKE_DATABASE")
    configured = identifier(database, "configured database")
    resolved = target_database(manifest)
    if configured != resolved:
        raise ValueError(
            f"Configured database {configured!r} does not match dbt-resolved target database "
            f"{resolved!r}"
        )
    return configured


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"dbt manifest not found: {manifest_path}. Run `dbt parse` for this project first."
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in dbt manifest {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError(f"dbt manifest {manifest_path} must contain a JSON object")
    validate_manifest(manifest, manifest_path)
    return manifest


def validate_manifest(manifest: dict[str, Any], manifest_path: str | Path | None = None) -> None:
    metadata = manifest.get("metadata")
    schema_version = metadata.get("dbt_schema_version") if isinstance(metadata, dict) else None
    if not schema_version:
        location = f" in {manifest_path}" if manifest_path else ""
        raise ValueError(f"dbt manifest{location} is missing metadata.dbt_schema_version")
    version = str(schema_version).rstrip("/").split("/")[-1].removesuffix(".json")
    if version not in SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_MANIFEST_SCHEMA_VERSIONS))
        raise ValueError(
            f"Unsupported dbt manifest schema version {schema_version!r}; supported versions: "
            f"{supported}. Run a supported dbt version or upgrade dbt-cortex-agent."
        )


def _meta(obj: dict[str, Any]) -> dict[str, Any]:
    direct = obj.get("meta")
    if isinstance(direct, dict) and direct:
        return direct
    config = obj.get("config")
    configured = config.get("meta") if isinstance(config, dict) else None
    return configured if isinstance(configured, dict) else {}


def _relation_fqn(node: dict[str, Any]) -> str:
    database = str(node.get("database") or "")
    schema = str(node.get("schema") or "")
    relation = str(node.get("alias") or node.get("name") or "")
    if not all((database, schema, relation)):
        raise ValueError(f"Eval model is missing database, schema, or name: {node.get('unique_id')}")
    return fqn(f"{database}.{schema}.{relation}", "eval model")


def _model_agent_spec(node: dict[str, Any]) -> dict[str, Any]:
    compiled = node.get("compiled_code")
    if not isinstance(compiled, str) or not compiled.strip():
        return {}
    try:
        value = json.loads(compiled)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _stage_suffix(stage_path: str) -> Path:
    _, suffix = stage_path_parts(stage_path)
    return Path(suffix)


def stage_path_parts(value: str) -> tuple[str, str]:
    return stage_path(value, "skill stage path")


def local_skill_dir(project_dir: str | Path, stage_path: str) -> Path:
    project_path = Path(project_dir)
    suffix = _stage_suffix(stage_path)
    parts = suffix.parts
    if parts and parts[0] == "agents":
        if len(parts) < 3:
            raise ValueError(
                f"Private skill stage path must be agents/<agent>/<name>: {stage_path!r}"
            )
        return project_path / "models" / "agents" / parts[1] / "skills" / Path(*parts[2:])
    return project_path / "skills" / suffix


def cortex_agents(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    nodes = manifest.get("nodes") or {}
    for node in nodes.values():
        config = node.get("config") if isinstance(node, dict) else None
        if not isinstance(config, dict) or config.get("materialized") != "cortex_agent":
            continue
        agent_meta = _meta(node).get("cortex_agent", {})
        if agent_meta is None:
            agent_meta = {}
        if not isinstance(agent_meta, dict):
            raise ValueError(
                f"cortex_agent model {node.get('unique_id')!r} meta.cortex_agent must be a mapping"
            )
        if agent_meta.get("enabled") is False:
            continue
        name = node.get("name")
        if not name:
            raise ValueError("Enabled cortex_agent model is missing a name")
        database = identifier(str(node.get("database") or ""), "cortex_agent model database")
        schema = identifier(str(node.get("schema") or ""), "cortex_agent model schema")
        physical_name = identifier(
            str(node.get("alias") or name), f"physical Agent for {name}"
        )
        normalized_meta = {
            **agent_meta,
            "compiled_spec": _model_agent_spec(node),
            "snowflake_name": physical_name,
            "naming": {**(agent_meta.get("naming") or {}), "__model__": physical_name},
        }
        agents.append(
            {
                "name": str(name),
                "meta": normalized_meta,
                "resource_type": "model",
                "unique_id": node.get("unique_id"),
                "physical_fqn": f"{database}.{schema}.{physical_name}",
            }
        )
    exposures = manifest.get("exposures") or {}
    for exposure in exposures.values():
        agent_meta = _meta(exposure).get("cortex_agent", {})
        if isinstance(agent_meta, dict) and agent_meta.get("enabled"):
            name = exposure.get("name")
            if not name:
                raise ValueError("Enabled cortex_agent exposure is missing a name")
            agents.append(
                {
                    "name": str(name),
                    "meta": agent_meta,
                    "resource_type": "exposure",
                    "unique_id": exposure.get("unique_id"),
                }
            )
    return sorted(agents, key=lambda item: item["name"])


def select_agents(
    manifest: dict[str, Any], names: list[str] | tuple[str, ...] | None = None
) -> list[dict[str, Any]]:
    agents = cortex_agents(manifest)
    by_name: dict[str, list[dict[str, Any]]] = {}
    for agent in agents:
        by_name.setdefault(agent["name"], []).append(agent)
    duplicates = sorted(name for name, values in by_name.items() if len(values) > 1)
    if duplicates:
        raise ValueError(
            "Enabled cortex_agent model/exposure names must be unique: "
            f"{', '.join(duplicates)}"
        )
    physical: dict[str, list[str]] = {}
    for agent in agents:
        physical_name = agent.get("physical_fqn")
        if physical_name:
            physical.setdefault(str(physical_name).upper(), []).append(agent["name"])
    duplicate_physical = sorted(
        name for name, logical_names in physical.items() if len(logical_names) > 1
    )
    if duplicate_physical:
        raise ValueError(
            "Enabled cortex_agent physical identities must be unique: "
            f"{', '.join(duplicate_physical)}"
        )
    if not names:
        return agents
    requested = list(dict.fromkeys(names))
    missing = sorted(set(requested) - set(by_name))
    if missing:
        available = ", ".join(sorted(by_name)) or "none"
        raise ValueError(
            f"Unknown enabled cortex_agent selection: {', '.join(missing)}; available: {available}"
        )
    return [by_name[name][0] for name in requested]


def skill_declarations(
    manifest: dict[str, Any], project_dir: str | Path, agent_names: list[str] | None = None
) -> list[SkillDeclaration]:
    declarations: list[SkillDeclaration] = []
    for agent in select_agents(manifest, agent_names):
        configured = agent["meta"].get("skills") or []
        spec_skills = agent["meta"].get("compiled_spec", {}).get("skills") or []
        legacy_skills = (agent["meta"].get("capabilities") or {}).get("skills") or []
        skills = configured or spec_skills or legacy_skills
        for skill in skills:
            source = skill.get("source") or {}
            if str(source.get("type", "")).lower() != "stage":
                continue
            stage_path = source.get("path")
            if not stage_path or not skill.get("name"):
                raise ValueError(f"Agent {agent['name']!r} has an incomplete stage skill declaration")
            declarations.append(
                SkillDeclaration(
                    agent_name=agent["name"],
                    skill_name=skill["name"],
                    source_type=source["type"],
                    stage_path=stage_path,
                    local_dir=local_skill_dir(project_dir, stage_path),
                )
            )
    return declarations


def cortex_evals(manifest: dict[str, Any]) -> list[EvalDeclaration]:
    declarations: list[EvalDeclaration] = []
    nodes = manifest.get("nodes") or {}
    for node in nodes.values():
        eval_meta = _meta(node).get("cortex_eval")
        if isinstance(eval_meta, dict) and eval_meta and eval_meta.get("enabled") is not False:
            declarations.append(
                EvalDeclaration(
                    model_name=node["name"], table_fqn=_relation_fqn(node), meta=eval_meta
                )
            )
    return sorted(declarations, key=lambda item: item.model_name)


def physical_agent_name(agent: dict[str, Any], target: str | None) -> str:
    if agent.get("resource_type") == "model":
        return identifier(
            agent["meta"].get("snowflake_name"),
            f"physical Agent for {agent['name']}",
        )
    meta = agent["meta"]
    naming = meta.get("naming") or {}
    value = naming.get(target) if target else meta.get("snowflake_name")
    if not value:
        requirement = f"cortex_agent.naming.{target}" if target else "cortex_agent.snowflake_name"
        raise ValueError(
            f"Physical Agent is unresolved for logical Agent {agent['name']!r}; declare "
            f"{requirement} so smoke does not guess macro suffix behavior"
        )
    return identifier(value, f"physical Agent for {agent['name']}")