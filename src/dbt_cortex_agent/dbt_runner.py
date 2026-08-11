from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


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
        kwargs = {"cwd": cwd, "text": True, "capture_output": True, "check": False}
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
) -> subprocess.CompletedProcess[str]:
    command = [executable, "parse", "--project-dir", str(project_dir)]
    if target:
        command.extend(["--target", target])
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