from __future__ import annotations

import subprocess

from .dbt_runner import CommandRunner


def connection_test(
    executable: str, connection: str, runner: CommandRunner
) -> subprocess.CompletedProcess[str]:
    return runner.run([executable, "connection", "test", "--connection", connection])