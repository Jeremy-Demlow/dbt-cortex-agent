from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .dbt_runner import CommandRunner
from .manifest import SkillDeclaration, select_agents, skill_declarations, stage_path_parts


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
    for agent in select_agents(manifest, agent_names):
        names: set[str] = set()
        configured = agent["meta"].get("skills") or []
        spec_skills = agent["meta"].get("compiled_spec", {}).get("skills") or []
        for skill in configured or spec_skills:
            skill_name = skill.get("name")
            if skill_name in names:
                raise ValueError(
                    f"Agent {agent['name']!r} declares duplicate skill name {skill_name!r}"
                )
            if skill_name:
                names.add(skill_name)
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
                f"Skill stage path collision for {declaration.stage_path}: {prior[1]} and {local_dir}"
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
) -> None:
    command_runner = runner or CommandRunner()
    target_database = config.database.upper() if config.database else ""
    for upload in plan:
        if stage_database(upload.stage_path).upper() != target_database:
            raise ValueError(
                f"Skill stage {upload.stage_path} targets database "
                f"{stage_database(upload.stage_path)!r}, not {config.database!r}"
            )

    validated: set[str] = set()
    for upload in plan:
        stage_key = upload.stage_fqn.casefold()
        if stage_key in validated:
            continue
        result = command_runner.run(
            [
                config.snow_executable,
                "sql",
                "--connection",
                str(config.connection),
                "--query",
                f"DESCRIBE STAGE {upload.stage_fqn}",
            ],
            cwd=config.project_dir,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "stage is missing"
            raise RuntimeError(
                f"Skill stage {upload.stage_fqn} is missing or inaccessible; "
                "provision it through the environment infrastructure owner before "
                f"uploading skills: {detail}"
            )
        validated.add(stage_key)

    for upload in plan:
        result = command_runner.run(
            [
                config.snow_executable,
                "stage",
                "copy",
                "--connection",
                str(config.connection),
                str(upload.local_dir / "*"),
                f"{upload.stage_path}/",
                "--overwrite",
                "--recursive",
                "--parallel",
                "4",
            ],
            cwd=config.project_dir,
        )
        if result.returncode != 0:
            names = ", ".join(upload.skill_names)
            raise RuntimeError(
                result.stderr.strip() or result.stdout.strip() or f"skill upload failed: {names}"
            )
