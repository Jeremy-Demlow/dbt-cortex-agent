from __future__ import annotations

from pathlib import Path
from typing import Any

from .compare import compare_results
from ..artifacts import contained_path
from .results import load_result


def baseline_path(baseline_dir: str | Path, agent: str, suite: str) -> Path:
    return contained_path(baseline_dir, agent, f"{suite}.json")


def gate_candidate(
    candidate_path: str | Path,
    *,
    baseline: str | Path | None = None,
    baseline_dir: str | Path | None = None,
    default_tolerance: float = 0.01,
) -> dict[str, Any]:
    candidate = load_result(candidate_path, "candidate")
    if baseline is None:
        if baseline_dir is None or not candidate.get("agent") or not candidate.get("suite"):
            raise ValueError("Gate requires --baseline or a baseline directory plus candidate agent/suite")
        baseline = baseline_path(baseline_dir, candidate["agent"], candidate["suite"])
    return compare_results(load_result(baseline, "baseline"), candidate, default_tolerance)