from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "requirements/REQ-013_single_physical_agent_evaluation.md"
INDEX = ROOT / "requirements/README.md"
STORIES = ROOT / "requirements/user_stories.md"
TEST_CASES = ROOT / "tests/test_cases.md"
SUPERSEDED_REQUIREMENTS = (
    ROOT / "requirements/REQ-005_dbt_rendered_eval_plan.md",
    ROOT / "requirements/REQ-011_tutorial_product_readiness.md",
    ROOT / "requirements/REQ-012_guided_cortex_code_adoption_skill.md",
)


def test_req_013_has_complete_requirements_first_structure() -> None:
    text = REQ.read_text(encoding="utf-8")
    for heading in (
        "## Status",
        "## Summary",
        "## Business context",
        "## Objective",
        "## Acceptance criteria",
        "## User stories",
        "## Dependencies",
        "## Out of scope",
        "## Notes",
    ):
        assert heading in text
    assert "Task 6 starter, project-skill, and active-documentation" in text
    assert "Verifier: substituted by focused requirement and documentation contract tests" in text


def test_req_013_contracts_optional_metadata_one_fqn_and_no_eval_lifecycle() -> None:
    text = REQ.read_text(encoding="utf-8")
    required = (
        "with no evaluation metadata validates, renders, and deploys normally",
        "Evaluation metadata is optional",
        "exactly one\n   physical Agent FQN",
        "Evaluation never creates, deploys, clones, suffixes, replaces",
        "cannot alter the\n   deployed Agent specification or trigger Agent lifecycle work",
        "has no physical canonical/native-eval projection split",
    )
    assert all(phrase in text for phrase in required)


def test_req_013_task_5_capability_semantics_are_explicit() -> None:
    text = REQ.read_text(encoding="utf-8")
    for phrase in (
        "Task 5 objective",
        "Native Agent evaluation `expected_tools` may name only declared Analyst, Cortex Search",
        "generic custom tools",
        "rejects skill, MCP, `code_execution`",
        "`StaffingSimulator` is eligible for native tool ground truth",
        "`evaluation_supported` is not a render/deploy selector",
    ):
        assert phrase in text


def test_req_013_classifies_capability_proof_and_records_direct_probes() -> None:
    text = REQ.read_text(encoding="utf-8")
    for classification in (
        "`attached`",
        "`invoked`",
        "`completed_with_attachment`",
        "`absent`",
        "`indeterminate`",
    ):
        assert classification in text
    for evidence in (
        "`RESORT_EXECUTIVE_DBT_FOCUS` completed 7 records",
        "zero errors and two attached skills",
        "`SKI_OPS_ASSISTANT_DBT_FOCUS` completed 16 records",
        "zero errors or warnings",
        "Cortex Search, web search, data-to-chart",
        "`StaffingSimulator`",
        "did not include\n  `code_execution`",
        "MCP attachment is `indeterminate`",
        "MCP is not called",
    ):
        assert evidence in text
    assert "This requirements-only\n  slice does not reconnect to Snowflake" in text


def test_req_013_supersedes_projection_baselines_without_rewriting_history() -> None:
    requirement = REQ.read_text(encoding="utf-8")
    assert "Historical `_EVAL` Agent runs and artifacts remain auditable migration evidence" in requirement
    assert "superseded histories rather than candidate or accepted baselines" in requirement
    for path in SUPERSEDED_REQUIREMENTS:
        text = path.read_text(encoding="utf-8")
        assert "Superseded" in text
        assert "REQ-013 supersedes" in text
        assert "historical" in text


def test_req_013_is_linked_from_requirements_stories_and_test_cases() -> None:
    index = INDEX.read_text(encoding="utf-8")
    stories = STORIES.read_text(encoding="utf-8")
    test_cases = TEST_CASES.read_text(encoding="utf-8")
    assert "REQ-013_single_physical_agent_evaluation.md" in index
    assert "## REQ-013" in stories
    assert "## REQ-013: single physical Agent evaluation" in test_cases
    assert "old `_EVAL` histories" in stories
    assert "Run focused Agent/deploy/CLI/macro tests and offline dbt parse" in test_cases


def test_req_013_task_6_starter_and_docs_scope_is_explicit() -> None:
    text = REQ.read_text(encoding="utf-8")
    for phrase in (
        "optional\n    eval model uses a descriptive suite model name",
        "never proposes a second Agent or a `native_eval` deployment",
        "Agent-only\n  path",
        "no\n    page claims that version 0.3.1 is currently available from PyPI",
        "Historical requirement, regression, and release-history references",
    ):
        assert phrase in text