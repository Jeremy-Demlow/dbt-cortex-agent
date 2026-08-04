from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .config import Config, load_yaml_mapping
from .dbt_runner import CommandRunner, executable_version
from .manifest import cortex_agents, cortex_evals, load_manifest, skill_declarations
from .snow import connection_test


@dataclass(frozen=True)
class Diagnostic:
    name: str
    status: str
    detail: str


def _declared_revisions(project_dir: Path) -> list[str]:
    revisions: list[str] = []
    for filename in ("packages.yml", "package-lock.yml"):
        document = load_yaml_mapping(project_dir / filename, strict=False)
        for item in document.get("packages", []) or []:
            if not isinstance(item, dict):
                continue
            source = str(item.get("git") or item.get("package") or "")
            if "dbt-cortex-agent" in source or "dbt_cortex_agent" in source:
                revision = item.get("revision") or item.get("version")
                if revision:
                    revisions.append(str(revision).removeprefix("v"))
    return revisions


def _dbt_package_versions(project_dir: Path) -> list[str]:
    versions: list[str] = []
    candidates = (
        Path(__file__).resolve().parents[2] / "dbt_project.yml",
        project_dir / "dbt_packages" / "dbt_cortex_agent" / "dbt_project.yml",
    )
    for candidate in candidates:
        project = load_yaml_mapping(candidate, strict=False)
        if project.get("name") == "dbt_cortex_agent" and project.get("version"):
            versions.append(str(project["version"]).removeprefix("v"))
    return versions


def run_doctor(config: Config, runner: CommandRunner | None = None) -> list[Diagnostic]:
    command_runner = runner or CommandRunner()
    diagnostics: list[Diagnostic] = []
    for name, executable in (("dbt executable", config.dbt_executable), ("snow executable", config.snow_executable)):
        try:
            result = executable_version(executable, command_runner)
        except OSError as exc:
            diagnostics.append(Diagnostic(name, "FAIL", str(exc)))
            continue
        output = result.stdout.strip() or result.stderr.strip()
        diagnostics.append(
            Diagnostic(name, "PASS" if result.returncode == 0 else "FAIL", output)
        )

    dbt_package_versions = _dbt_package_versions(config.project_dir)
    if dbt_package_versions:
        mismatches = sorted({version for version in dbt_package_versions if version != __version__})
        diagnostics.append(
            Diagnostic(
                "installed package version",
                "FAIL" if mismatches else "PASS",
                f"CLI={__version__}; dbt={', '.join(sorted(set(dbt_package_versions)))}",
            )
        )

    manifest: dict[str, Any] | None = None
    try:
        manifest = load_manifest(config.manifest)
        diagnostics.append(Diagnostic("manifest v12", "PASS", str(config.manifest)))
    except (FileNotFoundError, ValueError, OSError) as exc:
        diagnostics.append(Diagnostic("manifest v12", "FAIL", str(exc)))

    revisions = _declared_revisions(config.project_dir)
    if revisions:
        mismatches = sorted({version for version in revisions if version != __version__})
        diagnostics.append(
            Diagnostic(
                "consumer package version",
                "FAIL" if mismatches else "PASS",
                f"CLI={__version__}; declared={', '.join(sorted(set(revisions)))}",
            )
        )
    else:
        diagnostics.append(
            Diagnostic("consumer package version", "WARN", "no package version metadata found")
        )

    if manifest:
        agents = cortex_agents(manifest)
        evals = cortex_evals(manifest)
        diagnostics.append(
            Diagnostic("enabled Agents", "PASS", ", ".join(item["name"] for item in agents) or "none")
        )
        diagnostics.append(
            Diagnostic("enabled evals", "PASS", ", ".join(item.model_name for item in evals) or "none")
        )
        try:
            skills = skill_declarations(manifest, config.project_dir)
            missing = [str(item.local_dir) for item in skills if not item.local_dir.is_dir()]
            diagnostics.append(
                Diagnostic(
                    "configured local skills",
                    "FAIL" if missing else "PASS",
                    "missing: " + ", ".join(missing) if missing else f"{len(skills)} found",
                )
            )
        except ValueError as exc:
            diagnostics.append(Diagnostic("configured local skills", "FAIL", str(exc)))

    project = load_yaml_mapping(config.project_dir / "dbt_project.yml", strict=False)
    variables = project.get("vars") if isinstance(project.get("vars"), dict) else {}
    legacy_target = variables.get("cortex_agent_deploy_target")
    allowed_targets = variables.get("cortex_agent_allowed_targets") or (
        [legacy_target] if legacy_target else []
    )
    allowed_databases = variables.get("cortex_agent_allowed_databases") or []
    if not allowed_targets or not allowed_databases:
        diagnostics.append(
            Diagnostic(
                "deployment safety",
                "FAIL",
                "cortex_agent_allowed_targets and cortex_agent_allowed_databases must be non-empty; "
                "configure them explicitly or preview init with --target and --allow-database",
            )
        )
    elif not config.target:
        diagnostics.append(
            Diagnostic(
                "deployment safety",
                "WARN",
                f"allowed targets={allowed_targets}; allowed databases={allowed_databases}; "
                "active target unknown, supply --target to check it",
            )
        )
    elif config.target not in allowed_targets:
        diagnostics.append(
            Diagnostic(
                "deployment safety",
                "PASS",
                f"active target {config.target!r} cannot mutate allowlisted targets {allowed_targets}",
            )
        )
    else:
        diagnostics.append(
            Diagnostic(
                "deployment safety",
                "PASS",
                f"active target is allowed; databases={allowed_databases}",
            )
        )

    if config.connection_explicit and config.connection:
        try:
            result = connection_test(config.snow_executable, config.connection, command_runner)
            output = result.stdout.strip() or result.stderr.strip()
            diagnostics.append(
                Diagnostic("Snowflake connection", "PASS" if result.returncode == 0 else "FAIL", output)
            )
        except OSError as exc:
            diagnostics.append(Diagnostic("Snowflake connection", "FAIL", str(exc)))
    else:
        diagnostics.append(
            Diagnostic("Snowflake connection", "SKIP", "no explicit --connection supplied")
        )
    return diagnostics


def diagnostics_json(diagnostics: list[Diagnostic]) -> str:
    return json.dumps([item.__dict__ for item in diagnostics], indent=2)