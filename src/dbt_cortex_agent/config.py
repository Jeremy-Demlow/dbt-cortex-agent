from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True)
class Config:
    project_dir: Path
    manifest: Path
    target: str | None
    connection: str | None
    connection_explicit: bool
    database: str | None
    schema: str | None
    warehouse: str | None
    artifact_dir: Path
    dbt_executable: str
    snow_executable: str


def load_yaml_mapping(path: Path, *, strict: bool = True) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if value is None:
        return {}
    if not isinstance(value, dict):
        if strict:
            raise ValueError(f"Expected a YAML mapping in {path}")
        return {}
    return value


def _value(explicit: str | None, env: Mapping[str, str], name: str) -> str | None:
    return explicit if explicit is not None else env.get(name)


def resolve_config(args: object, env: Mapping[str, str] | None = None) -> Config:
    values = os.environ if env is None else env
    project_dir = Path(
        _value(getattr(args, "project_dir", None), values, "DBT_PROJECT_DIR") or "."
    ).expanduser().resolve()
    manifest_value = _value(getattr(args, "manifest", None), values, "DBT_MANIFEST")
    artifact_value = _value(
        getattr(args, "artifact_dir", None), values, "DBT_CORTEX_AGENT_ARTIFACT_DIR"
    )
    manifest = Path(manifest_value).expanduser() if manifest_value else Path("target/manifest.json")
    artifact_dir = Path(artifact_value).expanduser() if artifact_value else Path("target/dbt_cortex_agent")

    return Config(
        project_dir=project_dir,
        manifest=manifest.resolve() if manifest.is_absolute() else (project_dir / manifest).resolve(),
        target=_value(getattr(args, "target", None), values, "DBT_TARGET"),
        connection=_value(getattr(args, "connection", None), values, "SNOWFLAKE_CONNECTION_NAME"),
        connection_explicit=getattr(args, "connection", None) is not None,
        database=_value(getattr(args, "database", None), values, "SNOWFLAKE_DATABASE"),
        schema=_value(getattr(args, "schema", None), values, "SNOWFLAKE_SCHEMA"),
        warehouse=_value(getattr(args, "warehouse", None), values, "SNOWFLAKE_WAREHOUSE"),
        artifact_dir=(
            artifact_dir.resolve()
            if artifact_dir.is_absolute()
            else (project_dir / artifact_dir).resolve()
        ),
        dbt_executable=_value(
            getattr(args, "dbt_executable", None), values, "DBT_EXECUTABLE"
        )
        or "dbt",
        snow_executable=_value(
            getattr(args, "snow_executable", None), values, "SNOW_EXECUTABLE"
        )
        or "snow",
    )