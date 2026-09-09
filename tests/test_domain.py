from __future__ import annotations

import pytest

# Evidence: TC-021-01 TC-021-03 TC-021-04 TC-021-05
from dbt_cortex_agent.domain import (
    AgentVersionSelector,
    LifecyclePhase,
    OperationOutcome,
    SnowflakeObjectName,
    VersionKind,
    finite_number,
    is_controlled_operation_error,
)


def test_snowflake_object_name_is_validated_and_normalized() -> None:
    name = SnowflakeObjectName.parse("analytics.agents.finance")

    assert str(name) == "ANALYTICS.AGENTS.FINANCE"
    with pytest.raises(ValueError):
        SnowflakeObjectName.parse("analytics.agents.bad-name")


@pytest.mark.parametrize(
    ("value", "normalized", "kind"),
    [
        ("version$2", "VERSION$2", VersionKind.COMMITTED),
        ("default", "DEFAULT", VersionKind.SHORTCUT),
        ("LIVE", "LIVE", VersionKind.SHORTCUT),
        ("production", "PRODUCTION", VersionKind.ALIAS),
    ],
)
def test_agent_version_selector_classifies_safe_values(value, normalized, kind) -> None:
    selector = AgentVersionSelector.parse(value)

    assert selector.value == normalized
    assert selector.kind is kind


@pytest.mark.parametrize("value", ["VERSION$0", "bad-version", "prod;drop", ""])
def test_agent_version_selector_rejects_unsafe_values(value) -> None:
    with pytest.raises(ValueError):
        AgentVersionSelector.parse(value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "-Infinity", True, None])
def test_finite_number_rejects_non_finite_or_non_numeric_values(value) -> None:
    with pytest.raises(ValueError, match="score must be a finite number"):
        finite_number(value, "score")


def test_operation_outcome_preserves_durable_phase_order() -> None:
    outcome = (
        OperationOutcome()
        .complete(LifecyclePhase.PREFLIGHT)
        .complete(LifecyclePhase.VERSION_COMMITTED, "VERSION$2")
        .fail(LifecyclePhase.ALIAS_RECONCILED, "alias conflict")
    )

    assert outcome.to_dict() == [
        {"phase": "preflight", "completed": True},
        {"phase": "version_committed", "completed": True, "detail": "VERSION$2"},
        {"phase": "alias_reconciled", "completed": False, "detail": "alias conflict"},
    ]


# Evidence: TC-031-01 TC-031-02 TC-031-03
@pytest.mark.parametrize("error", [OSError("io"), RuntimeError("runtime"), ValueError("value")])
def test_controlled_operation_error_recognizes_expected_failures(error: Exception) -> None:
    assert is_controlled_operation_error(error)


def test_controlled_operation_error_recognizes_snowflake_connector_failures() -> None:
    ConnectorError = type(
        "ConnectorError", (Exception,), {"__module__": "snowflake.connector.errors"}
    )

    assert is_controlled_operation_error(ConnectorError("connector"))


def test_controlled_operation_error_rejects_programming_defects() -> None:
    assert not is_controlled_operation_error(AssertionError("programming defect"))
