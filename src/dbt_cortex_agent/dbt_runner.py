from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


RunCallable = Callable[..., subprocess.CompletedProcess[str]]


@dataclass
class CommandRunner:
    run_callable: RunCallable = subprocess.run

    def run(
        self, command: Sequence[str], *, cwd: str | Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        return self.run_callable(
            list(command), cwd=cwd, text=True, capture_output=True, check=False
        )


def executable_version(executable: str, runner: CommandRunner) -> subprocess.CompletedProcess[str]:
    return runner.run([executable, "--version"])


def run_dbt_deps(
    executable: str, project_dir: str | Path, target: str | None, runner: CommandRunner
) -> subprocess.CompletedProcess[str]:
    command = [executable, "deps", "--project-dir", str(project_dir)]
    if target:
        command.extend(["--target", target])
    return runner.run(command, cwd=project_dir)


def run_dbt_parse(
    executable: str, project_dir: str | Path, target: str | None, runner: CommandRunner
) -> subprocess.CompletedProcess[str]:
    command = [executable, "parse", "--project-dir", str(project_dir)]
    if target:
        command.extend(["--target", target])
    return runner.run(command, cwd=project_dir)


def run_dbt_operation(
    executable: str,
    project_dir: str | Path,
    target: str | None,
    macro: str,
    arguments: dict[str, object],
    runner: CommandRunner,
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
    return runner.run(command, cwd=project_dir)