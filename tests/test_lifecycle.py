from __future__ import annotations

import json
import subprocess

import pytest

from dbt_cortex_agent.lifecycle import (
    apply_route_plan,
    build_route_plan,
    drop_agent,
    read_version_state,
)

AGENT = {
    "name": "finance_assistant",
    "physical_fqn": "DB.AGENTS.FINANCE_ASSISTANT",
}

# Evidence: TC-023-06 TC-025-01 TC-025-02 TC-025-03 TC-025-04 TC-025-05
# Evidence: TC-025-11 TC-025-12 TC-030-03 TC-031-05
# Evidence: TC-032-02


class Runner:
    def __init__(self, prefix, payload):
        self.prefix = prefix
        self.payload = payload
        self.calls = []

    def run(self, command, **kwargs):
        self.calls.append(command)
        return subprocess.CompletedProcess(
            command, 0, f"{self.prefix}{json.dumps(self.payload)}\n", ""
        )


class SequencedRunner:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def run(self, command, **kwargs):
        self.calls.append(command)
        return next(self.results)


def test_route_plan_requires_committed_version_and_safe_alias() -> None:
    plan = build_route_plan("rollback", AGENT, "version$1", "production", True)

    assert plan.to_version == "VERSION$1"
    assert plan.alias == "PRODUCTION"
    assert str(plan.agent_fqn) == "DB.AGENTS.FINANCE_ASSISTANT"
    with pytest.raises(ValueError, match=r"VERSION\$N"):
        build_route_plan("promote", AGENT, "LAST", "production", False)
    with pytest.raises(ValueError, match="unquoted"):
        build_route_plan("promote", AGENT, "VERSION$2", "bad-alias", False)
    for reserved in ("DEFAULT", "FIRST", "LAST", "LIVE"):
        with pytest.raises(ValueError, match="reserved"):
            build_route_plan("promote", AGENT, "VERSION$2", reserved, False)


def test_version_state_uses_read_only_dbt_macro(config) -> None:
    payload = {"agent_fqn": "DB.AGENTS.A", "versions": ["VERSION$1"]}
    runner = Runner("CORTEX_AGENT_VERSION_STATE=", payload)

    assert read_version_state(config, "agent", runner=runner) == payload
    assert "dbt_cortex_agent.cortex_agent__version_state_for_model" in runner.calls[0]


def test_route_and_drop_delegate_to_dbt_macros(config) -> None:
    planned_state = {
        "agent_fqn": AGENT["physical_fqn"],
        "aliases": {"PRODUCTION": "VERSION$1", "DEFAULT": "VERSION$1"},
        "default_version": "VERSION$1",
    }
    alias_payload = {"after": {"aliases": {"PRODUCTION": "VERSION$2"}}}
    default_payload = {"after": {"default_version": "VERSION$2"}}
    route_runner = SequencedRunner(
        (
            subprocess.CompletedProcess(
                [], 0, f"CORTEX_AGENT_VERSION_STATE={json.dumps(planned_state)}\n", ""
            ),
            subprocess.CompletedProcess(
                [], 0, f"CORTEX_AGENT_ROUTE_RESULT={json.dumps(alias_payload)}\n", ""
            ),
            subprocess.CompletedProcess(
                [], 0, f"CORTEX_AGENT_DEFAULT_ROUTE_RESULT={json.dumps(default_payload)}\n", ""
            ),
        )
    )
    plan = build_route_plan("promote", AGENT, "VERSION$2", "production", True)

    result = apply_route_plan(config, plan, runner=route_runner)

    assert result["status"] == "completed"
    assert result["after"]["default_version"] == "VERSION$2"
    assert [phase["status"] for phase in result["phases"]] == ["completed", "completed"]
    assert "dbt_cortex_agent.cortex_agent__version_state_for_model" in route_runner.calls[0]
    assert "dbt_cortex_agent.cortex_agent__route_alias" in route_runner.calls[1]
    assert "dbt_cortex_agent.cortex_agent__route_default" in route_runner.calls[2]
    for command in route_runner.calls[1:]:
        arguments = json.loads(command[command.index("--args") + 1])
        assert arguments["expected_agent_fqn"] == AGENT["physical_fqn"]

    drop_payload = {"dropped": True}
    drop_runner = Runner("CORTEX_AGENT_DROP_RESULT=", drop_payload)
    assert (
        drop_agent(config, "finance_assistant", AGENT["physical_fqn"], runner=drop_runner)
        == drop_payload
    )
    assert "dbt_cortex_agent.cortex_agent__drop" in drop_runner.calls[0]
    command = drop_runner.calls[0]
    assert (
        json.loads(command[command.index("--args") + 1])["expected_agent_fqn"]
        == AGENT["physical_fqn"]
    )


@pytest.mark.parametrize(
    "observed", [None, "DB.OTHER.FINANCE_ASSISTANT", "OTHER.AGENTS.FINANCE_ASSISTANT"]
)
def test_route_rejects_inspected_identity_mismatch(config, observed):
    runner = Runner("CORTEX_AGENT_VERSION_STATE=", {"agent_fqn": observed})
    plan = build_route_plan("promote", AGENT, "VERSION$2", "production", True)
    with pytest.raises(ValueError, match="identity changed|inspected Agent FQN"):
        apply_route_plan(config, plan, runner=runner)
    assert len(runner.calls) == 1
    assert "dbt_cortex_agent.cortex_agent__version_state_for_model" in runner.calls[0]


def test_route_reports_alias_success_when_default_fails_and_retry_converges(config) -> None:
    alias_state = {
        "agent_fqn": AGENT["physical_fqn"],
        "aliases": {"PRODUCTION": "VERSION$2", "DEFAULT": "VERSION$1"},
        "default_version": "VERSION$1",
    }
    alias_payload = {"after": alias_state}
    failed_runner = SequencedRunner(
        (
            subprocess.CompletedProcess(
                [], 0, f"CORTEX_AGENT_VERSION_STATE={json.dumps(alias_state)}\n", ""
            ),
            subprocess.CompletedProcess(
                [], 0, f"CORTEX_AGENT_ROUTE_RESULT={json.dumps(alias_payload)}\n", ""
            ),
            subprocess.CompletedProcess([], 1, "", "DEFAULT update failed"),
            subprocess.CompletedProcess(
                [], 0, f"CORTEX_AGENT_VERSION_STATE={json.dumps(alias_state)}\n", ""
            ),
        )
    )
    plan = build_route_plan("rollback", AGENT, "VERSION$2", "production", True)

    partial = apply_route_plan(config, plan, runner=failed_runner)

    assert partial["status"] == "partial_failure"
    assert partial["after"] == alias_state
    assert partial["phases"][0] == {
        "phase": "alias",
        "status": "completed",
        "state": alias_state,
    }
    assert partial["phases"][1]["status"] == "failed"
    assert partial["phases"][1]["state"] == alias_state

    converged_state = {
        "aliases": {"PRODUCTION": "VERSION$2", "DEFAULT": "VERSION$2"},
        "default_version": "VERSION$2",
    }
    retry_runner = SequencedRunner(
        (
            subprocess.CompletedProcess(
                [], 0, f"CORTEX_AGENT_VERSION_STATE={json.dumps(alias_state)}\n", ""
            ),
            subprocess.CompletedProcess(
                [], 0, f"CORTEX_AGENT_ROUTE_RESULT={json.dumps(alias_payload)}\n", ""
            ),
            subprocess.CompletedProcess(
                [],
                0,
                f"CORTEX_AGENT_DEFAULT_ROUTE_RESULT={json.dumps({'after': converged_state})}\n",
                "",
            ),
        )
    )

    retried = apply_route_plan(config, plan, runner=retry_runner)

    assert retried["status"] == "completed"
    assert retried["after"] == converged_state


def test_route_reports_observed_state_when_alias_phase_fails(config) -> None:
    observed_state = {
        "agent_fqn": AGENT["physical_fqn"],
        "aliases": {"DEFAULT": "VERSION$1"},
        "default_version": "VERSION$1",
    }
    runner = SequencedRunner(
        (
            subprocess.CompletedProcess(
                [], 0, f"CORTEX_AGENT_VERSION_STATE={json.dumps(observed_state)}\n", ""
            ),
            subprocess.CompletedProcess([], 1, "", "alias assignment failed"),
            subprocess.CompletedProcess(
                [], 0, f"CORTEX_AGENT_VERSION_STATE={json.dumps(observed_state)}\n", ""
            ),
        )
    )
    plan = build_route_plan("promote", AGENT, "VERSION$2", "production", True)

    result = apply_route_plan(config, plan, runner=runner)

    assert result["status"] == "partial_failure"
    assert result["after"] == observed_state
    assert result["phases"][0]["phase"] == "alias"
    assert result["phases"][0]["status"] == "failed"


def test_route_programming_error_is_not_reported_as_partial_failure(config) -> None:
    class BrokenRunner:
        def run(self, command, **kwargs):
            raise AssertionError("programming defect")

    plan = build_route_plan("promote", AGENT, "VERSION$2", "production", True)
    with pytest.raises(AssertionError, match="programming defect"):
        apply_route_plan(config, plan, runner=BrokenRunner())


def test_retirement_without_acknowledgement_reports_unknown(config):
    class UnavailableRunner:
        def run(self, command, **kwargs):
            raise OSError("subprocess unavailable")

    result = drop_agent(
        config, "finance_assistant", AGENT["physical_fqn"], runner=UnavailableRunner()
    )
    assert result["status"] == "partial_failure"
    assert result["drop_status"] == "unknown"
    assert result["dropped"] is None
    assert result["before"] is None
    assert result["after"] is None


@pytest.mark.parametrize("bad_marker", ["{broken", '{"agent_fqn": "DB.OTHER.AGENT"}', "[]"])
def test_retirement_preserves_completion_if_later_evidence_is_malformed(config, bad_marker):
    evidence = {
        "agent_fqn": AGENT["physical_fqn"],
        "drop_status": "completed",
        "before": {"exists": True},
        "after": None,
        "dropped": True,
    }
    runner = SequencedRunner(
        [
            subprocess.CompletedProcess(
                [],
                1,
                "CORTEX_AGENT_DROP_EVIDENCE=" + json.dumps(evidence),
                "CORTEX_AGENT_DROP_EVIDENCE=" + bad_marker,
            )
        ]
    )
    result = drop_agent(config, "finance_assistant", AGENT["physical_fqn"], runner=runner)
    assert result["status"] == "partial_failure"
    assert result["drop_status"] == "completed"
    assert result["before"] == {"exists": True}
    assert result["after"] is None


def test_retirement_duplicate_stream_markers_do_not_erase_observed_state(config):
    evidence = {
        "agent_fqn": AGENT["physical_fqn"],
        "drop_status": "completed",
        "before": {"exists": True},
        "after": {"exists": True},
        "dropped": True,
    }
    duplicate = {**evidence, "after": None}
    runner = SequencedRunner(
        [
            subprocess.CompletedProcess(
                [],
                1,
                "CORTEX_AGENT_DROP_EVIDENCE=" + json.dumps(evidence),
                "CORTEX_AGENT_DROP_EVIDENCE=" + json.dumps(duplicate),
            )
        ]
    )
    result = drop_agent(config, "finance_assistant", AGENT["physical_fqn"], runner=runner)
    assert result["drop_status"] == "completed"
    assert result["after"] == {"exists": True}


@pytest.fixture
def config(tmp_path):
    from argparse import Namespace

    from dbt_cortex_agent.config import resolve_config

    return resolve_config(
        Namespace(
            project_dir=str(tmp_path),
            manifest=None,
            target="sandbox",
            connection="conn",
            database="DB",
            schema=None,
            role=None,
            warehouse=None,
            artifact_dir=None,
            dbt_executable="dbt",
            snow_executable="snow",
        ),
        env={},
    )
