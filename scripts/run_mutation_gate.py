from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Evidence: TC-021-09


@dataclass(frozen=True)
class Mutation:
    name: str
    path: str
    original: str
    replacement: str
    expected_failure: str


MUTATIONS = (
    Mutation(
        "identifier skips validation",
        "src/dbt_cortex_agent/identifiers.py",
        "if not _IDENTIFIER.fullmatch(text):",
        "if False:",
        "test_identifier_mutation_contract",
    ),
    Mutation(
        "FQN accepts wrong cardinality",
        "src/dbt_cortex_agent/identifiers.py",
        "if len(values) != parts:",
        "if False:",
        "test_fqn_mutation_contract",
    ),
    Mutation(
        "stage path permits traversal",
        "src/dbt_cortex_agent/identifiers.py",
        'part in {"", ".", ".."}',
        'part in {""}',
        "test_stage_path_mutation_contract",
    ),
    Mutation(
        "finite-number check accepts infinity",
        "src/dbt_cortex_agent/domain.py",
        "if not math.isfinite(number):",
        "if False:",
        "test_domain_mutation_contract",
    ),
    Mutation(
        "version selector treats shortcuts as aliases",
        "src/dbt_cortex_agent/domain.py",
        'if upper in {"DEFAULT", "FIRST", "LAST", "LIVE"}:',
        "if False:",
        "test_domain_mutation_contract",
    ),
    Mutation(
        "comparison ignores regression tolerance",
        "src/dbt_cortex_agent/eval/compare.py",
        "delta < -tolerance",
        "False",
        "test_compare_mutation_contract",
    ),
)


def _apply_mutation(project: Path, mutation: Mutation) -> None:
    path = project / mutation.path
    source = path.read_text(encoding="utf-8")
    if source.count(mutation.original) != 1:
        raise RuntimeError(
            f"Mutation {mutation.name!r} expected one source match in {mutation.path}"
        )
    path.write_text(source.replace(mutation.original, mutation.replacement), encoding="utf-8")


def _assert_killed(mutation: Mutation) -> None:
    with tempfile.TemporaryDirectory(prefix="dbt-cortex-agent-mutation-") as temporary:
        project = Path(temporary) / "project"
        shutil.copytree(ROOT / "src", project / "src")
        shutil.copytree(ROOT / "tests", project / "tests")
        _apply_mutation(project, mutation)
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(project / "src")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests/test_mutation_targets.py"],
            cwd=project,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        if result.returncode == 0:
            raise RuntimeError(f"Mutation survived: {mutation.name}")
        if result.returncode not in {1}:
            raise RuntimeError(
                f"Mutation test infrastructure failed for {mutation.name}: {output[-2000:]}"
            )
        if mutation.expected_failure not in output:
            raise RuntimeError(
                f"Mutation {mutation.name!r} failed for an unexpected reason: {output[-2000:]}"
            )


def main() -> int:
    for mutation in MUTATIONS:
        _assert_killed(mutation)
        print(f"KILLED: {mutation.name}", flush=True)
    print(f"Killed {len(MUTATIONS)} safety-critical mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
