from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
import json
from pathlib import Path
from typing import Any

from . import __version__
from .config import Config, load_yaml_mapping
from .dbt_runner import CommandRunner, run_dbt_deps


DEFAULT_REVISION = f"v{__version__}"
STARTER_ORDERS = "orders"
SEMANTIC_VIEW_PACKAGE = {
    "package": "Snowflake-Labs/dbt_semantic_view",
    "version": "1.0.5",
}
STARTER_PATHS = (
    "models/semantic/sem_orders.sql",
    "models/agents/orders_assistant/agent.yml",
    "models/agents/orders_assistant/evals/orders_assistant_core.sql",
    "models/agents/orders_assistant/evals/core.yml",
    "seeds/orders.csv",
    "seeds/orders.yml",
)
DBTIGNORE_STARTER_ENTRY = "models/agents/*/skills/**"


@dataclass(frozen=True)
class InitAction:
    path: Path
    action: str


@dataclass(frozen=True)
class InitResult:
    changed_files: tuple[Path, ...]
    messages: tuple[str, ...]
    actions: tuple[InitAction, ...] = ()


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


def _semantic_view_package_matches(item: object) -> bool:
    return isinstance(item, dict) and item.get("package") == SEMANTIC_VIEW_PACKAGE["package"]


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
    starter: str | None = None,
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
    if starter == STARTER_ORDERS:
        if any(_semantic_view_package_matches(item) for item in package_items):
            messages.append("packages.yml already declares dbt_semantic_view; leaving it unchanged")
        else:
            package_items.append(dict(SEMANTIC_VIEW_PACKAGE))
            messages.append(
                "packages.yml: append missing semantic-view dependency:\n"
                f"  - package: {SEMANTIC_VIEW_PACKAGE['package']}\n"
                f"    version: {SEMANTIC_VIEW_PACKAGE['version']}"
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


def _append_semantic_view_package_text(text: str) -> str:
    addition = (
        f"  - package: {SEMANTIC_VIEW_PACKAGE['package']}\n"
        f"    version: {SEMANTIC_VIEW_PACKAGE['version']}\n"
    )
    return _insert_before_next_top_level(text, "packages", addition)


def _append_vars_text(text: str, additions: dict[str, Any]) -> str:
    rendered = "".join(f"  {key}: {json.dumps(value)}\n" for key, value in additions.items())
    return _insert_before_next_top_level(text, "vars", rendered)


def _starter_contents(starter: str) -> dict[str, str]:
    if starter != STARTER_ORDERS:
        raise ValueError(f"Unsupported starter: {starter}")
    root = files("dbt_cortex_agent").joinpath("starters", starter)
    return {
        path: root.joinpath(path).read_text(encoding="utf-8").rstrip("\n") + "\n"
        for path in STARTER_PATHS
    }


def _append_line(text: str, line: str) -> str:
    if line in {item.strip() for item in text.splitlines()}:
        return text
    separator = "" if not text or text.endswith("\n") else "\n"
    return f"{text}{separator}{line}\n"


def _validate_parent_directories(project_dir: Path, destinations: list[Path]) -> None:
    for destination in destinations:
        parent = destination.parent
        while parent != project_dir:
            if parent.exists() and not parent.is_dir():
                raise FileExistsError(
                    f"Orders starter collision at {parent}; expected a directory"
                )
            parent = parent.parent


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
    starter: str | None = None,
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
        starter=starter,
    )
    writes: dict[Path, str] = {}
    actions: list[InitAction] = []
    package_items = original_packages.get("packages", []) or []
    if not any(_package_matches(item, package_source) for item in package_items):
        current = packages_path.read_text(encoding="utf-8") if packages_path.exists() else ""
        writes[packages_path] = _append_package_text(current, str(package_source), revision)
        actions.append(InitAction(packages_path, "append" if packages_path.exists() else "create"))
    if starter == STARTER_ORDERS and not any(
        _semantic_view_package_matches(item) for item in package_items
    ):
        current = writes.get(
            packages_path,
            packages_path.read_text(encoding="utf-8") if packages_path.exists() else "",
        )
        writes[packages_path] = _append_semantic_view_package_text(current)
        if not any(action.path == packages_path for action in actions):
            actions.append(InitAction(packages_path, "append" if packages_path.exists() else "create"))

    existing_vars = original_project.get("vars", {}) or {}
    desired_vars = project.get("vars", {})
    missing_vars = {key: value for key, value in desired_vars.items() if key not in existing_vars}
    if missing_vars:
        writes[project_path] = _append_vars_text(
            project_path.read_text(encoding="utf-8"), missing_vars
        )
        actions.append(InitAction(project_path, "append"))

    if starter == STARTER_ORDERS:
        for relative_path, content in _starter_contents(starter).items():
            destination = config.project_dir / relative_path
            if destination.exists():
                if not destination.is_file() or destination.read_text(encoding="utf-8") != content:
                    raise FileExistsError(
                        f"Orders starter collision at {destination}; existing content differs"
                    )
                actions.append(InitAction(destination, "unchanged"))
            else:
                writes[destination] = content
                actions.append(InitAction(destination, "create"))

        dbtignore_path = config.project_dir / ".dbtignore"
        current_ignore = dbtignore_path.read_text(encoding="utf-8") if dbtignore_path.exists() else ""
        updated_ignore = _append_line(current_ignore, DBTIGNORE_STARTER_ENTRY)
        if updated_ignore == current_ignore:
            actions.append(InitAction(dbtignore_path, "unchanged"))
        else:
            writes[dbtignore_path] = updated_ignore
            actions.append(
                InitAction(dbtignore_path, "append" if dbtignore_path.exists() else "create")
            )
        _validate_parent_directories(config.project_dir, list(writes))

    changed: list[Path] = []
    if apply:
        for path, content in writes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            changed.append(path)
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
    if starter == STARTER_ORDERS:
        messages.append("Orders starter plan validated; all collisions were checked before writes")
    return InitResult(tuple(changed), tuple(messages), tuple(actions))