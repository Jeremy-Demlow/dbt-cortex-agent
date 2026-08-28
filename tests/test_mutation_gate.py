from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]

# Evidence: TC-021-09
SPEC = importlib.util.spec_from_file_location(
    "run_mutation_gate", ROOT / "scripts/run_mutation_gate.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_mutation_gate_kills_named_validator_mutant_without_touching_source() -> None:
    mutation = MODULE.MUTATIONS[0]
    source = ROOT / mutation.path
    before = _digest(source)

    MODULE._assert_killed(mutation)

    assert _digest(source) == before
