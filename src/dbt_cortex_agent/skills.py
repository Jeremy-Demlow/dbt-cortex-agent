from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import shutil
import tempfile
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
from .manifest import (
    SKILL_MODE_IMMUTABLE,
    SKILL_MODE_OVERWRITE,
    SkillDeclaration,
    skill_declarations,
    stage_path_parts,
)

DIGEST_VAR = "cortex_agent_skill_digests"
DIGEST_PREFIX = "sha256-"
DIGEST_LENGTH = 16
_SAFE_FILE_PART = re.compile(r"^[A-Za-z0-9_$.-]+$")


@dataclass(frozen=True)
class SkillFile:
    relative_path: str
    size: int
    md5: str


@dataclass(frozen=True)
class SkillUpload:
    stage_fqn: str
    stage_path: str
    local_dir: Path
    skill_names: tuple[str, ...]
    agent_names: tuple[str, ...]
    mode: str = SKILL_MODE_IMMUTABLE
    files: tuple[SkillFile, ...] = ()
    digest: str | None = None

    @property
    def deployed_path(self) -> str:
        """The folder a committed Agent version reads this skill from."""
        return f"{self.stage_path}/{self.digest}" if self.digest else self.stage_path

    @property
    def rollback_restores_skill_text(self) -> bool:
        return self.mode == SKILL_MODE_IMMUTABLE


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


def skill_inventory(local_dir: Path) -> tuple[tuple[SkillFile, ...], str]:
    """Return the files a skill upload publishes and their content digest.

    Hidden files and folders (for example ``.DS_Store``) are not part of a skill.
    The digest covers sorted relative paths and file bytes, so it is stable
    across machines and changes whenever any published file changes.
    """
    files: list[SkillFile] = []
    content = hashlib.sha256()
    for path in sorted(local_dir.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(local_dir)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Skill folder {local_dir} contains a symlink: {relative}")
        if not path.is_file():
            continue
        if not all(_SAFE_FILE_PART.fullmatch(part) for part in relative.parts):
            raise ValueError(
                f"Skill file name {relative.as_posix()!r} in {local_dir} must use only "
                "letters, digits, '_', '$', '.', or '-'"
            )
        data = path.read_bytes()
        name = relative.as_posix()
        files.append(
            SkillFile(name, len(data), hashlib.md5(data, usedforsecurity=False).hexdigest())
        )
        content.update(f"{name}\0{len(data)}\0{hashlib.sha256(data).hexdigest()}\n".encode())
    return tuple(files), DIGEST_PREFIX + content.hexdigest()[:DIGEST_LENGTH]


def build_upload_plan(
    manifest: dict, project_dir: str | Path, agent_names: list[str] | None = None
) -> list[SkillUpload]:
    project_path = Path(project_dir).resolve()
    declarations = [
        item
        for item in skill_declarations(manifest, project_path, agent_names)
        if item.source_type == "stage"
    ]
    stage_sources: dict[str, tuple[str, Path, str]] = {}
    grouped: dict[str, list[SkillDeclaration]] = {}

    for declaration in declarations:
        _stage_parts(declaration.stage_path)
        if declaration.local_dir is None:
            raise ValueError(f"Stage skill {declaration.skill_name!r} has no local folder")
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
        if prior is not None and prior[2] != declaration.mode:
            raise ValueError(
                f"Skill stage path {declaration.stage_path} is declared with both "
                f"{prior[2]!r} and {declaration.mode!r} modes; shared skills need one mode"
            )
        if prior is None:
            stage_sources[collision_key] = (declaration.stage_path, local_dir, declaration.mode)
        grouped.setdefault(collision_key, []).append(declaration)

    plan: list[SkillUpload] = []
    for collision_key, values in grouped.items():
        stage_path, local_dir, mode = stage_sources[collision_key]
        stage_fqn, _ = _stage_parts(stage_path)
        files, digest = skill_inventory(local_dir)
        plan.append(
            SkillUpload(
                stage_fqn=stage_fqn,
                stage_path=stage_path,
                local_dir=local_dir,
                skill_names=tuple(sorted({item.skill_name for item in values})),
                agent_names=tuple(sorted({item.agent_name for item in values})),
                mode=mode,
                files=files,
                digest=digest if mode == SKILL_MODE_IMMUTABLE else None,
            )
        )
    return sorted(plan, key=lambda item: item.stage_path.casefold())


def skill_digests(plan: list[SkillUpload] | tuple[SkillUpload, ...]) -> dict[str, str]:
    """The dbt var that points each immutable base path at its content folder."""
    return {item.stage_path: item.digest for item in plan if item.digest}


def upload_payload(item: SkillUpload) -> dict[str, object]:
    payload: dict[str, object] = {
        "stage_path": item.stage_path,
        "deployed_path": item.deployed_path,
        "mode": item.mode,
        "rollback_restores_skill_text": item.rollback_restores_skill_text,
        "local_dir": str(item.local_dir),
        "skills": list(item.skill_names),
        "agents": list(item.agent_names),
    }
    if item.mode == SKILL_MODE_OVERWRITE:
        payload["warning"] = (
            "overwrite mode replaces the staged files in place; rolling an Agent back "
            "to an earlier version serves the current skill text"
        )
    return payload


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


def _run_checked(runner: CommandRunner, command: list[str], config: Config, failure: str) -> str:
    result = runner.run(command, cwd=config.project_dir)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or failure)
    return result.stdout


def _staged_files(
    upload: SkillUpload, config: Config, runner: CommandRunner, role_args: list[str]
) -> dict[str, tuple[int, str]]:
    """Read back the deployed folder as relative path -> (size, md5)."""
    folder = upload.deployed_path
    output = _run_checked(
        runner,
        [
            config.snow_executable,
            "sql",
            "--connection",
            str(config.connection),
            *role_args,
            "--format",
            "JSON",
            "--query",
            f"LIST {folder}/",
        ],
        config,
        "stage listing failed",
    )
    try:
        rows = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Unreadable LIST output for {folder}") from exc
    if not isinstance(rows, list):
        raise RuntimeError(f"Unreadable LIST output for {folder}")
    # LIST names are "<stage name>/<folder>/<file>"; strip the stage segment.
    prefix = folder.split("/", 1)[1] + "/"
    staged: dict[str, tuple[int, str]] = {}
    for row in rows:
        name = row.get("name") if isinstance(row, dict) else None
        size = row.get("size") if isinstance(row, dict) else None
        md5 = row.get("md5") if isinstance(row, dict) else None
        remainder = name.split("/", 1)[1] if isinstance(name, str) and "/" in name else ""
        if not remainder.startswith(prefix) or not isinstance(size, int) or not md5:
            raise RuntimeError(f"Unexpected LIST entry {row!r} for {folder}")
        staged[remainder[len(prefix) :]] = (size, str(md5))
    return staged


def _verify(upload: SkillUpload, staged: dict[str, tuple[int, str]], *, exact: bool) -> None:
    expected = {item.relative_path: (item.size, item.md5) for item in upload.files}
    different = sorted(name for name, value in expected.items() if staged.get(name) != value)
    extra = sorted(set(staged) - set(expected)) if exact else []
    if different or extra:
        raise RuntimeError(
            f"Staged files at {upload.deployed_path} do not match {upload.local_dir}: "
            f"missing or different {different or 'none'}; unexpected {extra or 'none'}"
        )


def _copy(upload: SkillUpload, config: Config, runner: CommandRunner, role_args: list[str]) -> None:
    # Upload exactly the inventoried files so the stage cannot gain hidden files
    # that the content digest does not describe.
    with tempfile.TemporaryDirectory(prefix="dbt-cortex-agent-skill-") as scratch:
        root = Path(scratch)
        for item in upload.files:
            destination = root / item.relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(upload.local_dir / item.relative_path, destination)
        _run_checked(
            runner,
            [
                config.snow_executable,
                "stage",
                "copy",
                "--connection",
                str(config.connection),
                *role_args,
                str(root / "*"),
                f"{upload.deployed_path}/",
                "--overwrite" if upload.mode == SKILL_MODE_OVERWRITE else "--no-overwrite",
                "--no-auto-compress",
                "--recursive",
                "--parallel",
                "4",
            ],
            config,
            "skill upload failed",
        )


def _publish(
    upload: SkillUpload, config: Config, runner: CommandRunner, role_args: list[str]
) -> str:
    if upload.mode == SKILL_MODE_OVERWRITE:
        _copy(upload, config, runner, role_args)
        _verify(upload, _staged_files(upload, config, runner, role_args), exact=False)
        return "overwritten"
    staged = _staged_files(upload, config, runner, role_args)
    expected = {item.relative_path: (item.size, item.md5) for item in upload.files}
    if staged == expected:
        return "reused"
    conflicts = sorted(name for name, value in staged.items() if expected.get(name) != value)
    if conflicts:
        raise RuntimeError(
            f"Refusing to reuse {upload.deployed_path}: existing files {conflicts} differ "
            "from the local skill. Content folders are never overwritten; inspect and "
            "remove the folder deliberately if it was tampered with."
        )
    # Empty, or a subset left by an interrupted upload: copy without overwrite.
    _copy(upload, config, runner, role_args)
    _verify(upload, _staged_files(upload, config, runner, role_args), exact=True)
    return "uploaded"


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
            _run_checked(command_runner, command, config, "stage is missing")
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
        try:
            detail = _publish(upload, config, command_runner, role_args)
        except Exception as exc:
            if not is_controlled_operation_error(exc) and not isinstance(exc, TimeoutExpired):
                raise
            message = (
                f"Skill copy failed for {upload.deployed_path}; partial effects possible: {exc}"
            )
            raise DurablePhaseError(
                message,
                outcome.fail(
                    LifecyclePhase.SKILLS_UPLOADED, message, stage_path=upload.deployed_path
                ),
            ) from exc
        outcome = outcome.complete(
            LifecyclePhase.SKILLS_UPLOADED, detail, stage_path=upload.deployed_path
        )
    return outcome
