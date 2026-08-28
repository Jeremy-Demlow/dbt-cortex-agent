from __future__ import annotations

import math

import pytest

from dbt_cortex_agent.domain import AgentVersionSelector, VersionKind, finite_number
from dbt_cortex_agent.eval.compare import compare_results
from dbt_cortex_agent.identifiers import fqn, identifier, stage_path, version


def test_identifier_mutation_contract() -> None:
    assert identifier("agent_$1") == "AGENT_$1"
    for invalid in ("", "1AGENT", "A-B", "A.B", "A B", "A;DROP", '"A"'):
        with pytest.raises(ValueError):
            identifier(invalid)


def test_fqn_mutation_contract() -> None:
    assert fqn("db.schema.agent", "Agent") == "DB.SCHEMA.AGENT"
    for invalid in ("DB.AGENT", "DB.SCHEMA.AGENT.EXTRA", "DB.BAD-SCHEMA.AGENT"):
        with pytest.raises(ValueError):
            fqn(invalid, "Agent")


def test_version_mutation_contract() -> None:
    assert version("version$42") == "VERSION$42"
    for invalid in ("VERSION$0", "VERSION$01", "VERSION$", "LAST", "VERSION$-1"):
        with pytest.raises(ValueError):
            version(invalid)


def test_stage_path_mutation_contract() -> None:
    assert stage_path("@db.schema.stage/agents/a-1") == (
        "DB.SCHEMA.STAGE",
        "agents/a-1",
    )
    for invalid in (
        "DB.SCHEMA.STAGE/path",
        "@DB.SCHEMA.STAGE",
        "@DB.SCHEMA.STAGE/",
        "@DB.SCHEMA.STAGE//x",
        "@DB.SCHEMA.STAGE/../x",
        "@DB.SCHEMA.STAGE/x y",
    ):
        with pytest.raises(ValueError):
            stage_path(invalid)


def test_domain_mutation_contract() -> None:
    assert AgentVersionSelector.parse("version$2") == AgentVersionSelector(
        "VERSION$2", VersionKind.COMMITTED
    )
    assert AgentVersionSelector.parse("last").kind is VersionKind.SHORTCUT
    assert AgentVersionSelector.parse("production") == AgentVersionSelector(
        "PRODUCTION", VersionKind.ALIAS
    )
    for invalid in (True, math.nan, math.inf, -math.inf, "not-a-number"):
        with pytest.raises(ValueError):
            finite_number(invalid, "value")
    assert finite_number("1.25", "value") == 1.25


def test_compare_mutation_contract() -> None:
    def artifact(score: float, artifact_type: str = "candidate") -> dict:
        identity = {
            "agent_name": "agent",
            "suite_name": "core",
            "eval_model": "agent_core",
            "agent_fqn": "DB.AGENTS.AGENT",
            "dataset_fqn": "DB.EVAL.DATA",
            "stage_fqn": "DB.AGENTS.STAGE",
        }
        return {
            "schema_version": 2,
            "artifact_type": artifact_type,
            "agent": "agent",
            "suite": "core",
            "eval_model": "agent_core",
            "run_name": "run",
            "timestamp": "20260828_000000",
            "summary": {"answer_correctness": {"avg": score, "n": 1}},
            "thresholds": {"answer_correctness": 0.80},
            "regression_tolerances": {"answer_correctness": 0.01},
            "passed": score >= 0.80,
            "total_records": 1,
            "plan_schema_version": 2,
            "suite_signature": "signature",
            "plan_identity": identity,
            "agent_fqn": "DB.AGENTS.AGENT",
            "dataset_fqn": "DB.EVAL.DATA",
            "stage_fqn": "DB.AGENTS.STAGE",
            "metric_names": ["answer_correctness"],
            "ordered_ground_truth_refs": ["ref"],
            "status": "completed",
            "run_metadata": {
                "plan_identity": identity,
                "evaluated_version": "VERSION$1",
                "pre_start": {"default_version": "VERSION$1"},
                "post_completion": {"default_version": "VERSION$1"},
                "default_version_changed": False,
            },
        }

    baseline = artifact(0.90, "baseline")
    passing = artifact(0.90)
    regressed = artifact(0.88)
    assert compare_results(baseline, passing, 0.01)["passed"] is True
    assert compare_results(baseline, regressed, 0.01)["passed"] is False
