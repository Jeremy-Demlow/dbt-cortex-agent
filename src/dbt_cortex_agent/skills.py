from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from subprocess import TimeoutExpired

from .config import Config
from .dbt_runner import CommandRunner
from .domain import (
    DurablePhaseError,
    LifecyclePhase,
    OperationOutcome,
    is_controlled_operation_error,
)
from .identifiers import identifier
from .manifest import SkillDeclaration, skill_declarations, stage_path_parts


@dataclass(frozen=True)
class SkillUpload:
    stage_fqn: str
    stage_path: str
    local_dir: Path
    skill_names: tuple[str, ...]
    agent_names: tuple[str, ...]


def _stage_parts(stage_path: str) -> tuple[str, str]:
    return stage_path_parts(stage_path)


def stage_database(stage_path: str) -> str:
    stage_fqn, _ = _stage_parts(stage_path)
    return stage_fqn.split(".", 1)[0]


def _ignored_private_skill(project_dir: Path, local_dir: Path) -> bool:
    try:
        relative = local_dir.resolve().relative_to(project_dir.resolve()).as_posix()
    except ValueError:
        return False
    if not relative.startswith("models/agents/") or "/skills/" not in relative:
        return True
    ignore_file = project_dir / ".dbtignore"
    if not ignore_file.is_file():
        return False
    candidate = f"{relative}/SKILL.md"
    patterns = [
        line.strip()
        for line in ignore_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and not line.startswith("!")
    ]
    return any(fnmatch.fnmatch(candidate, pattern) for pattern in patterns)


def build_upload_plan(
    manifest: dict, project_dir: str | Path, agent_names: list[str] | None = None
) -> list[SkillUpload]:
    project_path = Path(project_dir).resolve()
    declarations = skill_declarations(manifest, project_path, agent_names)
    stage_sources: dict[str, tuple[str, Path]] = {}
    grouped: dict[str, list[SkillDeclaration]] = {}

    for declaration in declarations:
        _stage_parts(declaration.stage_path)
        local_dir = declaration.local_dir.resolve()
        skill_file = local_dir / "SKILL.md"
        if not skill_file.is_file():
            raise FileNotFoundError(
                f"Declared skill {declaration.skill_name!r} for Agent "
                f"{declaration.agent_name!r} is missing {skill_file}"
            )
        if not _ignored_private_skill(project_path, local_dir):
            raise ValueError(
                f"Private skill directory {local_dir} is not protected by "
                f"{project_path / '.dbtignore'}"
            )
        collision_key = declaration.stage_path.casefold()
        prior = stage_sources.get(collision_key)
        if prior is not None and prior[1] != local_dir:
            raise ValueError(
                f"Skill stage path collision for {declaration.stage_path}: "
                f"{prior[1]} and {local_dir}"
            )
        if prior is None:
            stage_sources[collision_key] = (declaration.stage_path, local_dir)
        grouped.setdefault(collision_key, []).append(declaration)

    plan: list[SkillUpload] = []
    for collision_key, values in grouped.items():
        stage_path, local_dir = stage_sources[collision_key]
        stage_fqn, _ = _stage_parts(stage_path)
        plan.append(
            SkillUpload(
                stage_fqn=stage_fqn,
                stage_path=stage_path,
                local_dir=local_dir,
                skill_names=tuple(sorted({item.skill_name for item in values})),
                agent_names=tuple(sorted({item.agent_name for item in values})),
            )
        )
    return sorted(plan, key=lambda item: item.stage_path.casefold())


def assert_apply_safety(
    config: Config, allowed_targets: list[str], allowed_databases: list[str]
) -> None:
    if not config.target:
        raise ValueError("Apply requires an explicit --target or DBT_TARGET")
    if config.target not in allowed_targets:
        raise ValueError(
            f"Refusing apply for target {config.target!r}; allowed targets: "
            f"{', '.join(allowed_targets) or 'none'}"
        )
    if not config.database:
        raise ValueError("Apply requires an explicit --database or SNOWFLAKE_DATABASE")
    allowed = {name.upper() for name in allowed_databases}
    if config.database.upper() not in allowed:
        raise ValueError(
            f"Refusing apply for database {config.database!r}; allowed databases: "
            f"{', '.join(allowed_databases) or 'none'}"
        )
    if not config.connection_explicit or not config.connection:
        raise ValueError("Apply requires an explicitly supplied --connection")


def upload_skills(
    plan: list[SkillUpload], config: Config, runner: CommandRunner | None = None
) -> OperationOutcome:
    command_runner = runner or CommandRunner()
    outcome = OperationOutcome()
    role_args = ["--role", identifier(config.role, "skill role")] if config.role else []
    validated: set[str] = set()
    for upload in plan:
        stage_key = upload.stage_fqn.casefold()
        if stage_key in validated:
            continue
        command = [
            config.snow_executable,
            "sql",
            "--connection",
            str(config.connection),
            *role_args,
            "--query",
            f"DESCRIBE STAGE {upload.stage_fqn}",
        ]
        try:
            result = command_runner.run(command, cwd=config.project_dir)
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or "stage is missing"
                raise RuntimeError(detail)
        except Exception as exc:
            if not is_controlled_operation_error(exc) and not isinstance(exc, TimeoutExpired):
                raise
            message = (
                f"Skill stage {upload.stage_fqn} is missing or inaccessible; "
                "provision it through the environment infrastructure owner before "
                f"uploading skills: {exc}"
            )
            raise DurablePhaseError(
                message,
                outcome.fail(LifecyclePhase.PREFLIGHT, message, stage_path=upload.stage_path),
            ) from exc
        validated.add(stage_key)

    for upload in plan:
        command = [
            config.snow_executable,
            "stage",
            "copy",
            "--connection",
            str(config.connection),
            *role_args,
            str(upload.local_dir / "*"),
            f"{upload.stage_path}/",
            "--overwrite",
            "--recursive",
            "--parallel",
            "4",
        ]
        try:
            result = command_runner.run(command, cwd=config.project_dir)
            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr.strip() or result.stdout.strip() or "skill upload failed"
                )
        except Exception as exc:
            if not is_controlled_operation_error(exc) and not isinstance(exc, TimeoutExpired):
                raise
            message = f"Skill copy failed for {upload.stage_path}; partial effects possible: {exc}"
            raise DurablePhaseError(
                message,
                outcome.fail(LifecyclePhase.SKILLS_UPLOADED, message, stage_path=upload.stage_path),
            ) from exc
        outcome = outcome.complete(LifecyclePhase.SKILLS_UPLOADED, stage_path=upload.stage_path)
    return outcome
