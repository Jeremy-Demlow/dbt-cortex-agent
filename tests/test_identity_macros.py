from __future__ import annotations

import copy
import json
import subprocess
from types import SimpleNamespace

import pytest

from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.lifecycle import apply_route_plan, build_route_plan, drop_agent

FQN = "DB.DEV_AGENTS.PHYSICAL_AGENT"

# Evidence: TC-032-03 TC-032-05


@pytest.fixture
def routing(macro_harness):
    node = SimpleNamespace(
        resource_type="model",
        name="assistant",
        alias="PHYSICAL_AGENT",
        database="DB",
        schema="DEV_AGENTS",
        config={"materialized": "cortex_agent", "schema": "AGENTS"},
    )
    state = {
        "agent_fqn": FQN,
        "exists": True,
        "versions": ["VERSION$1", "VERSION$2"],
        "aliases": {"PRODUCTION": "VERSION$1"},
        "default_version": "VERSION$1",
    }
    effects = []

    def query(sql):
        effects.append(sql)
        if "UNSET ALIAS" in sql:
            state["aliases"].pop("PRODUCTION")
        elif "SET ALIAS" in sql:
            state["aliases"]["PRODUCTION"] = "VERSION$2"
        elif "SET DEFAULT_VERSION" in sql:
            state["default_version"] = "VERSION$2"
        elif sql.startswith("DROP"):
            state["exists"] = False
        else:
            pytest.fail(f"Unexpected query: {sql}")

    macro_harness.context.update(
        graph=SimpleNamespace(nodes={"model.fixture.assistant": node}),
        target=SimpleNamespace(name="sandbox", database="DB"),
        var=lambda name, default=None: {
            "cortex_agent_allowed_targets": ["sandbox"],
            "cortex_agent_allowed_databases": ["DB", "OTHER_DB"],
        }.get(name, default),
        run_query=query,
    )
    macro_harness.override("cortex_agent__version_state", lambda fqn: copy.deepcopy(state))
    return macro_harness, effects, node, state


CASES = [
    (
        "route_alias",
        {
            "agent_name": "assistant",
            "to_version": "VERSION$2",
            "alias": "production",
            "expected_alias_version": "VERSION$1",
        },
    ),
    (
        "route_alias_for_fqn",
        {
            "agent_fqn": FQN,
            "to_version": "VERSION$2",
            "alias": "production",
            "expected_alias_version": "VERSION$1",
        },
    ),
    (
        "route_default",
        {
            "agent_name": "assistant",
            "to_version": "VERSION$2",
            "expected_default_version": "VERSION$1",
        },
    ),
    (
        "route_version",
        {
            "agent_name": "assistant",
            "to_version": "VERSION$2",
            "alias": "production",
            "set_default": True,
        },
    ),
    ("drop", {"agent_name": "assistant"}),
]


@pytest.mark.parametrize("macro,arguments", CASES)
@pytest.mark.parametrize(
    "expected",
    ["OTHER_DB.DEV_AGENTS.PHYSICAL_AGENT", "DB.OTHER.PHYSICAL_AGENT", "DB.DEV_AGENTS.OTHER", ""],
)
def test_mismatched_identity_blocks_before_mutation(routing, macro, arguments, expected):
    harness, effects, _, _ = routing
    with pytest.raises(ValueError, match="identity changed|three-part"):
        harness.call(f"cortex_agent__{macro}", **arguments, expected_agent_fqn=expected)
    assert effects == []


@pytest.mark.parametrize("macro,arguments", CASES)
@pytest.mark.parametrize("expected", [None, FQN.lower()])
def test_matching_and_legacy_calls_mutate_resolved_identity(routing, macro, arguments, expected):
    harness, effects, _, state = routing
    optional = {} if expected is None else {"expected_agent_fqn": expected}
    result = json.loads(harness.call(f"cortex_agent__{macro}", **arguments, **optional))
    assert result["agent_fqn"] == FQN
    assert effects
    assert all(FQN in sql for sql in effects)
    if macro == "route_version":
        assert state["default_version"] == "VERSION$2"
        assert len(effects) == 3
    if macro == "drop":
        assert state["exists"] is False


def test_composite_route_binds_default_after_graph_changes(routing):
    harness, effects, node, _ = routing
    original = harness.context["run_query"]

    def change_graph_after_alias(sql):
        original(sql)
        if "SET ALIAS" in sql:
            node.schema = "OTHER"

    harness.context["run_query"] = change_graph_after_alias
    with pytest.raises(ValueError, match="identity changed"):
        harness.call(
            "cortex_agent__route_version",
            "assistant",
            "VERSION$2",
            "production",
            set_default=True,
            expected_agent_fqn=FQN,
        )
    assert len(effects) == 2
    assert all(FQN in sql and "DEFAULT_VERSION" not in sql for sql in effects)


@pytest.mark.parametrize("changed_phase", ["route_alias", "route_default", "drop"])
def test_python_plan_is_enforced_by_mutating_macro(routing, tmp_path, changed_phase):
    harness, effects, node, _ = routing
    config = resolve_config(SimpleNamespace(project_dir=str(tmp_path), target="sandbox"), env={})

    def run_operation(command, **kwargs):
        macro = command[2].split(".")[-1]
        arguments = json.loads(command[command.index("--args") + 1])
        if macro == f"cortex_agent__{changed_phase}":
            node.schema = "OTHER"
        output = []
        harness.context["log"] = lambda message, **kwargs: output.append(message)
        try:
            harness.call(macro, **arguments)
        except ValueError as exc:
            return subprocess.CompletedProcess(command, 1, "\n".join(output), str(exc))
        return subprocess.CompletedProcess(command, 0, "\n".join(output), "")

    runner = CommandRunner(run_operation)
    if changed_phase == "drop":
        result = drop_agent(config, "assistant", FQN, runner=runner)
        assert result["status"] == "partial_failure"
        assert result["drop_status"] == "unknown"
        assert "identity changed" in result["error"]
    else:
        plan = build_route_plan(
            "promote",
            {"name": "assistant", "physical_fqn": FQN},
            "VERSION$2",
            "production",
            True,
        )
        result = apply_route_plan(config, plan, runner=runner)
        assert result["status"] == "partial_failure"
        assert "identity changed" in result["error"]
    assert len(effects) == (2 if changed_phase == "route_default" else 0)
    assert all(FQN in sql and "DEFAULT_VERSION" not in sql for sql in effects)


@pytest.mark.parametrize("failure", ["drop_before", "drop_after", "inspect", "postcondition"])
@pytest.mark.parametrize("existed", [True, False])
def test_retirement_failure_evidence_and_retry(routing, tmp_path, failure, existed):
    harness, effects, _, state = routing
    state["exists"] = existed
    config = resolve_config(SimpleNamespace(project_dir=str(tmp_path), target="sandbox"), env={})
    before = copy.deepcopy(state)
    original_query = harness.context["run_query"]
    fail = True

    def query(sql):
        if fail and failure == "drop_before":
            raise RuntimeError("DROP rejected")
        original_query(sql)
        if fail and failure == "drop_after":
            raise OSError("DROP acknowledgement lost")

    def inspect(fqn):
        assert fqn == FQN
        if fail and effects:
            if failure == "inspect":
                raise RuntimeError("inspection unavailable")
            if failure == "postcondition":
                return {**copy.deepcopy(state), "exists": True}
        return copy.deepcopy(state)

    def run_operation(command, **kwargs):
        output = []
        harness.context["log"] = lambda message, **kwargs: output.append(message)
        arguments = json.loads(command[command.index("--args") + 1])
        try:
            harness.call(command[2].split(".")[-1], **arguments)
        except (OSError, RuntimeError, ValueError) as exc:
            return subprocess.CompletedProcess(command, 1, "\n".join(output), str(exc))
        return subprocess.CompletedProcess(command, 0, "\n".join(output), "")

    harness.context["run_query"] = query
    harness.override("cortex_agent__version_state", inspect)
    runner = CommandRunner(run_operation)
    result = drop_agent(config, "assistant", FQN, runner=runner)
    acknowledged = failure in {"inspect", "postcondition"}
    assert result["status"] == "partial_failure"
    assert result["before"] == before
    assert result["drop_status"] == ("completed" if acknowledged else "unknown")
    assert result["dropped"] is (existed if acknowledged else None)
    assert result["phases"][0]["status"] == result["drop_status"]
    if acknowledged:
        assert result["phases"][1] == {"phase": "verification", "status": "failed"}
    if failure == "postcondition":
        assert result["after"]["exists"] is True
    else:
        assert result["after"] is None

    fail = False
    retried = drop_agent(config, "assistant", FQN, runner=runner)
    assert retried["dropped"] is (existed and failure == "drop_before")
    assert retried["after"]["exists"] is False
    assert all(sql == f"DROP AGENT IF EXISTS {FQN}" for sql in effects)


@pytest.mark.parametrize("failure_point", ["drop", "inspection"])
@pytest.mark.parametrize("error_type", [AssertionError, TypeError, AttributeError])
def test_retirement_programming_errors_propagate(routing, tmp_path, failure_point, error_type):
    harness, effects, _, state = routing
    config = resolve_config(SimpleNamespace(project_dir=str(tmp_path), target="sandbox"), env={})
    original_query = harness.context["run_query"]

    def query(sql):
        if failure_point == "drop":
            raise error_type("programming defect")
        return original_query(sql)

    def inspect(fqn):
        if effects:
            raise error_type("programming defect")
        return copy.deepcopy(state)

    def run_operation(command, **kwargs):
        harness.call("cortex_agent__drop", "assistant", expected_agent_fqn=FQN)
        pytest.fail("programming defect was swallowed")

    harness.context["run_query"] = query
    harness.override("cortex_agent__version_state", inspect)
    with pytest.raises(error_type, match="programming defect"):
        drop_agent(config, "assistant", FQN, runner=CommandRunner(run_operation))
