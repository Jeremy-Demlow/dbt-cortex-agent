from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

RunCallable = Callable[..., subprocess.CompletedProcess[str]]


@dataclass
class CommandRunner:
    run_callable: RunCallable = subprocess.run

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        kwargs: dict[str, object] = {
            "cwd": cwd,
            "text": True,
            "capture_output": True,
            "check": False,
        }
        if env is not None:
            kwargs["env"] = dict(env)
        return self.run_callable(list(command), **kwargs)


def executable_version(executable: str, runner: CommandRunner) -> subprocess.CompletedProcess[str]:
    return runner.run([executable, "--version"])


def _run(
    runner: CommandRunner,
    command: Sequence[str],
    *,
    cwd: str | Path,
    env: Mapping[str, str] | None,
) -> subprocess.CompletedProcess[str]:
    if env is None:
        return runner.run(command, cwd=cwd)
    return runner.run(command, cwd=cwd, env=env)


def run_dbt_deps(
    executable: str,
    project_dir: str | Path,
    target: str | None,
    runner: CommandRunner,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [executable, "deps", "--project-dir", str(project_dir)]
    if target:
        command.extend(["--target", target])
    return _run(runner, command, cwd=project_dir, env=env)


def run_dbt_parse(
    executable: str,
    project_dir: str | Path,
    target: str | None,
    runner: CommandRunner,
    env: Mapping[str, str] | None = None,
    *,
    target_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [executable, "parse", "--project-dir", str(project_dir)]
    if target:
        command.extend(["--target", target])
    if target_path is not None:
        command.extend(["--target-path", str(target_path), "--write-json"])
    return _run(runner, command, cwd=project_dir, env=env)


def run_dbt_build(
    executable: str,
    project_dir: str | Path,
    target: str | None,
    selectors: Sequence[str],
    runner: CommandRunner,
    env: Mapping[str, str] | None = None,
    *,
    variables: Mapping[str, object] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [executable, "build", "--project-dir", str(project_dir)]
    if target:
        command.extend(["--target", target])
    command.extend(["--select", *selectors])
    if variables is not None:
        command.extend(["--vars", json.dumps(variables, separators=(",", ":"))])
    return _run(runner, command, cwd=project_dir, env=env)


def run_dbt_test(
    executable: str,
    project_dir: str | Path,
    target: str | None,
    selectors: Sequence[str],
    runner: CommandRunner,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [executable, "test", "--project-dir", str(project_dir)]
    if target:
        command.extend(["--target", target])
    command.extend(["--select", *selectors])
    return _run(runner, command, cwd=project_dir, env=env)


def run_dbt_operation(
    executable: str,
    project_dir: str | Path,
    target: str | None,
    macro: str,
    arguments: dict[str, object],
    runner: CommandRunner,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        executable,
        "run-operation",
        macro,
        "--args",
        json.dumps(arguments, separators=(",", ":")),
        "--project-dir",
        str(project_dir),
    ]
    if target:
        command.extend(["--target", target])
    return _run(runner, command, cwd=project_dir, env=env)
