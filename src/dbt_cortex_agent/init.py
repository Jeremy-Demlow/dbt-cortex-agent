from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from . import __version__
from .config import Config, load_yaml_mapping
from .dbt_runner import CommandRunner, run_dbt_deps


DEFAULT_REVISION = f"v{__version__}"


@dataclass(frozen=True)
class InitResult:
    changed_files: tuple[Path, ...]
    messages: tuple[str, ...]


def _package_matches(item: object, package_source: str | None) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("package") == "dbt_cortex_agent":
        return True
    local_source = str(item.get("local") or "").rstrip("/")
    if local_source and Path(local_source).name == "dbt_cortex_agent":
        return True
    if package_source is None:
        return False
    return str(item.get("git") or "").rstrip("/") == package_source.rstrip("/")


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def build_preview(
    config: Config,
    package_source: str | None = None,
    revision: str = DEFAULT_REVISION,
    *,
    target: str | None = None,
    allowed_targets: list[str] | None = None,
    allowed_databases: list[str] | None = None,
    agent_schema: str | None = None,
    eval_schema: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    packages_path = config.project_dir / "packages.yml"
    project_path = config.project_dir / "dbt_project.yml"
    packages = load_yaml_mapping(packages_path)
    project = load_yaml_mapping(project_path)
    package_items = packages.setdefault("packages", [])
    if not isinstance(package_items, list):
        raise ValueError(f"Expected packages to be a list in {packages_path}")
    messages: list[str] = []
    if any(_package_matches(item, package_source) for item in package_items):
        messages.append("packages.yml already declares dbt_cortex_agent; leaving it unchanged")
    else:
        if not package_source:
            raise ValueError(
                "No identifiable dbt_cortex_agent dependency found; supply --package-source"
            )
        package_items.append({"git": package_source, "revision": revision})
        messages.append(
            "packages.yml: append missing package snippet:\n"
            f"  - git: {json.dumps(package_source)}\n"
            f"    revision: {json.dumps(revision)}"
        )

    vars_config = project.setdefault("vars", {})
    if not isinstance(vars_config, dict):
        raise ValueError(f"Expected vars to be a mapping in {project_path}")
    allowed_targets = allowed_targets or []
    allowed_databases = allowed_databases or []
    if not target and (allowed_targets or allowed_databases):
        raise ValueError("--allow-target and --allow-database require an explicit --target")
    desired_vars: dict[str, Any] = {}
    if target:
        if not vars_config.get("cortex_agent_allowed_databases") and not allowed_databases:
            raise ValueError(
                "Adding deployment safety configuration requires at least one --allow-database"
            )
        desired_vars.update(
            {
                "cortex_agent_deploy_target": target,
                "cortex_agent_allowed_targets": _unique([target, *allowed_targets]),
                "cortex_agent_allowed_databases": _unique(allowed_databases),
            }
        )
    if agent_schema:
        desired_vars["cortex_agent_schema"] = agent_schema
    if eval_schema:
        desired_vars["cortex_eval_schema"] = eval_schema
    for key, value in desired_vars.items():
        if key in vars_config:
            messages.append(f"dbt_project.yml: keep existing var {key}")
        else:
            vars_config[key] = value
            messages.append(
                f"dbt_project.yml: append missing var snippet:\n  {key}: {json.dumps(value)}"
            )
    return packages, project, messages


def _insert_before_next_top_level(text: str, key: str, addition: str) -> str:
    lines = text.splitlines(keepends=True)
    start = next(
        (index for index, line in enumerate(lines) if line.startswith(f"{key}:")), None
    )
    if start is None:
        separator = "" if not text or text.endswith("\n") else "\n"
        return f"{text}{separator}{key}:\n{addition}"
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and not line.lstrip().startswith("#") and not line[0].isspace():
            end = index
            break
    lines.insert(end, addition)
    return "".join(lines)


def _append_package_text(text: str, package_source: str, revision: str) -> str:
    addition = (
        f"  - git: {json.dumps(package_source)}\n    revision: {json.dumps(revision)}\n"
    )
    return _insert_before_next_top_level(text, "packages", addition)


def _append_vars_text(text: str, additions: dict[str, Any]) -> str:
    rendered = "".join(f"  {key}: {json.dumps(value)}\n" for key, value in additions.items())
    return _insert_before_next_top_level(text, "vars", rendered)


def initialize(
    config: Config,
    *,
    apply: bool = False,
    run_deps: bool = False,
    package_source: str | None = None,
    revision: str = DEFAULT_REVISION,
    target: str | None = None,
    allowed_targets: list[str] | None = None,
    allowed_databases: list[str] | None = None,
    agent_schema: str | None = None,
    eval_schema: str | None = None,
    runner: CommandRunner | None = None,
) -> InitResult:
    if run_deps and not apply:
        raise ValueError("--run-dbt-deps requires --apply")
    if not config.project_dir.is_dir():
        raise FileNotFoundError(f"dbt project directory not found: {config.project_dir}")
    project_path = config.project_dir / "dbt_project.yml"
    if not project_path.is_file():
        raise FileNotFoundError(f"dbt_project.yml not found: {project_path}")

    packages_path = config.project_dir / "packages.yml"
    original_packages = load_yaml_mapping(packages_path)
    original_project = load_yaml_mapping(project_path)
    packages, project, messages = build_preview(
        config,
        package_source,
        revision,
        target=target,
        allowed_targets=allowed_targets,
        allowed_databases=allowed_databases,
        agent_schema=agent_schema,
        eval_schema=eval_schema,
    )
    changed: list[Path] = []
    if apply:
        package_items = original_packages.get("packages", []) or []
        if not any(_package_matches(item, package_source) for item in package_items):
            current = packages_path.read_text(encoding="utf-8") if packages_path.exists() else ""
            packages_path.write_text(
                _append_package_text(current, str(package_source), revision), encoding="utf-8"
            )
            changed.append(packages_path)

        existing_vars = original_project.get("vars", {}) or {}
        desired_vars = project.get("vars", {})
        missing_vars = {key: value for key, value in desired_vars.items() if key not in existing_vars}
        if missing_vars:
            current = project_path.read_text(encoding="utf-8")
            project_path.write_text(_append_vars_text(current, missing_vars), encoding="utf-8")
            changed.append(project_path)
        if run_deps:
            result = run_dbt_deps(
                config.dbt_executable, config.project_dir, config.target, runner or CommandRunner()
            )
            if result.returncode:
                detail = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(f"dbt deps failed ({result.returncode}): {detail}")
            messages.append("dbt deps completed")
    else:
        messages.insert(0, "Preview only; rerun with --apply to write changes")
    return InitResult(tuple(changed), tuple(messages))