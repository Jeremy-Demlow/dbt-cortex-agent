from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .domain import SnowflakeObjectName
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


def agent_database(agent: dict[str, Any]) -> str:
    return identifier(str(agent.get("database") or ""), f"database for {agent.get('name')}")


def agent_schema(agent: dict[str, Any]) -> str:
    return identifier(str(agent.get("schema") or ""), f"schema for {agent.get('name')}")


def selected_agent_databases(agents: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(sorted({agent_database(agent) for agent in agents}))


def assert_config_database(
    manifest: dict[str, Any], database: str | None, agent_names: list[str] | None = None
) -> str:
    """Compatibility assertion scoped to selected Agents, never unrelated models."""
    if not database:
        raise ValueError("Operation requires explicit --database or SNOWFLAKE_DATABASE")
    configured = identifier(database, "configured database")
    resolved = selected_agent_databases(select_agents(manifest, agent_names))
    if resolved != (configured,):
        raise ValueError(
            f"Configured database {configured!r} does not match selected Agent databases "
            f"{', '.join(resolved) or 'none'}"
        )
    return configured


def assert_resource_databases_allowed(
    databases: list[str] | tuple[str, ...] | set[str], allowed_databases: list[str]
) -> tuple[str, ...]:
    resolved = tuple(sorted({identifier(value, "resource database") for value in databases}))
    allowed = {identifier(value, "allowed database") for value in allowed_databases}
    missing = [value for value in resolved if value not in allowed]
    if missing:
        raise ValueError(
            "Refusing operation for resource databases not in the allowlist: "
            f"{', '.join(missing)}; allowed databases: {', '.join(sorted(allowed)) or 'none'}"
        )
    return resolved


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
        raise ValueError(
            f"Eval model is missing database, schema, or name: {node.get('unique_id')}"
        )
    return fqn(f"{database}.{schema}.{relation}", "eval model")


def _skill_text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or any(marker in value for marker in ("{{", "{%", "{#"))
    ):
        raise ValueError(f"{label} has an incomplete or unresolved skill declaration")
    return value


def _skill_contract(value: Any, label: str) -> dict[str, tuple[str, str]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of skill declarations")
    contract: dict[str, tuple[str, str]] = {}
    for skill in value:
        if not isinstance(skill, dict) or not isinstance(skill.get("source"), dict):
            raise ValueError(f"{label} requires skill mappings with a source mapping")
        name, source = _skill_text(skill.get("name"), label), skill["source"]
        source_type = _skill_text(source.get("type"), label).lower()
        path = _skill_text(source.get("path"), label)
        if name in contract:
            raise ValueError(f"{label} declares duplicate skill name {name!r}")
        if source_type == "stage":
            stage_fqn, suffix = stage_path_parts(path)
            path = f"@{stage_fqn}/{suffix}"
        contract[name] = (source_type, path)
    return contract


def _skill_spec_evidence(node: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    compiled = node.get("compiled_code")
    has_compiled = isinstance(compiled, str) and bool(compiled.strip())
    body = compiled if has_compiled else node.get("raw_code")
    if not isinstance(body, str) or not body.strip():
        return None, False
    detectable = "skills" in body
    if not has_compiled and any(marker in body for marker in ("{{", "{%", "{#")):
        return None, detectable
    try:
        spec = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        if has_compiled or detectable:
            raise ValueError(f"Agent {node['name']!r} has unreadable skill evidence") from exc
        return None, False
    if not isinstance(spec, dict):
        if has_compiled or detectable:
            raise ValueError(f"Agent {node['name']!r} specification must be a YAML mapping")
        return None, False
    return spec, detectable


def _agent_skill_contract(agent: dict[str, Any], node: dict[str, Any]) -> dict:
    label = f"Agent {agent['name']!r} meta.cortex_agent.skills"
    capabilities = agent["meta"].get("capabilities")
    if isinstance(capabilities, dict) and "skills" in capabilities:
        raise ValueError(f"{label} is required; capabilities.skills metadata is unsupported")
    configured = agent["meta"].get("skills", [])
    contract = _skill_contract(configured, label)
    spec, detectable = _skill_spec_evidence(node)
    if spec is None:
        if detectable and not contract:
            raise ValueError(f"{label} must explicitly resolve detectable model skills")
        return contract
    capabilities = spec.get("capabilities")
    if isinstance(capabilities, dict) and "skills" in capabilities:
        raise ValueError("Use native top-level skills, not capabilities.skills, in model YAML")
    declared = _skill_contract(spec.get("skills", []), f"Agent {agent['name']!r} model skills")
    if declared and "skills" not in agent["meta"]:
        raise ValueError(f"{label} is required for local skill uploads; YAML alone is insufficient")
    if contract != declared:
        raise ValueError(f"{label} does not match model skills (name, source type, or path)")
    return contract


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
        physical_name = identifier(str(node.get("alias") or name), f"physical Agent for {name}")
        normalized_meta = {
            **agent_meta,
            "snowflake_name": physical_name,
        }
        agents.append(
            {
                "name": str(name),
                "meta": normalized_meta,
                "resource_type": "model",
                "unique_id": node.get("unique_id"),
                "database": database,
                "schema": schema,
                "object_name": physical_name,
                "physical_fqn": f"{database}.{schema}.{physical_name}",
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
            f"Enabled cortex_agent model names must be unique: {', '.join(duplicates)}"
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
        node = manifest["nodes"][agent["unique_id"]]
        skills = _agent_skill_contract(agent, node)
        for skill_name, (source_type, path) in skills.items():
            if source_type != "stage":
                continue
            declarations.append(
                SkillDeclaration(
                    agent_name=agent["name"],
                    skill_name=skill_name,
                    source_type=source_type,
                    stage_path=path,
                    local_dir=local_skill_dir(project_dir, path),
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
    return identifier(
        agent["meta"].get("snowflake_name"),
        f"physical Agent for {agent['name']}",
    )


def physical_agent_fqn(agent: dict[str, Any]) -> str:
    return str(
        SnowflakeObjectName.parse(
            str(agent.get("physical_fqn") or ""),
            f"physical Agent for {agent.get('name')}",
        )
    )
