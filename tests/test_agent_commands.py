from __future__ import annotations

import argparse
import json

import pytest

# Evidence: TC-026-01 TC-026-02 TC-026-03 TC-026-05 TC-026-06 TC-026-09 TC-030-01 TC-030-02
from dbt_cortex_agent.commands.agent import (
    _handle_deploy,
    _handle_drop,
    _handle_route,
    _handle_smoke,
    _handle_versions,
)
from dbt_cortex_agent.config import Config
from dbt_cortex_agent.domain import DurablePhaseError, LifecyclePhase, OperationOutcome

AGENT = {
    "name": "finance_assistant",
    "unique_id": "model.fixture.finance_assistant",
    "database": "DB",
    "schema": "AGENTS",
    "object_name": "FINANCE_ASSISTANT",
    "physical_fqn": "DB.AGENTS.FINANCE_ASSISTANT",
}
MANIFEST = {
    "nodes": {
        AGENT["unique_id"]: {
            **AGENT,
            "resource_type": "model",
            "alias": AGENT["object_name"],
            "config": {"materialized": "cortex_agent"},
        }
    }
}


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        project_dir=tmp_path,
        manifest=tmp_path / "target/manifest.json",
        target="sandbox",
        connection="conn",
        connection_explicit=True,
        database="DB",
        database_explicit=True,
        schema="AGENTS",
        role="ROLE",
        warehouse="WH",
        warehouse_explicit=True,
        artifact_dir=tmp_path / "target/dbt_cortex_agent",
        dbt_executable="dbt",
        snow_executable="snow",
    )


def _args(command: str, **overrides) -> argparse.Namespace:
    values = {
        "agent_command": command,
        "agent": "finance_assistant",
        "agents": ["finance_assistant"],
        "apply": False,
        "json": True,
        "allow_target": ["sandbox"],
        "allow_database": ["DB"],
        "to_version": "VERSION$2",
        "alias": "production",
        "set_default": True,
        "confirm_agent": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_versions_handler_emits_read_only_state(monkeypatch, capsys, config) -> None:
    state = {"versions": ["VERSION$1", "VERSION$2"], "default_version": "VERSION$2"}
    monkeypatch.setattr("dbt_cortex_agent.commands.agent.read_version_state", lambda *_: state)

    assert _handle_versions(_args("versions"), config, MANIFEST) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["agent_fqn"] == AGENT["physical_fqn"]
    assert payload["state"] == state


@pytest.mark.parametrize("command", ["promote", "rollback"])
def test_route_preview_is_non_mutating(command, monkeypatch, capsys, config) -> None:
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.apply_route_plan",
        lambda *_: pytest.fail("preview invoked routing"),
    )

    assert _handle_route(_args(command), config, MANIFEST) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == f"agent {command}"
    assert payload["applied"] is False
    assert payload["result"] is None


def test_route_partial_failure_emits_json_and_exit_two(monkeypatch, capsys, config) -> None:
    result = {"status": "partial_failure", "phases": [{"phase": "alias"}]}
    monkeypatch.setattr("dbt_cortex_agent.commands.agent.apply_route_plan", lambda *_: result)

    assert _handle_route(_args("promote", apply=True), config, MANIFEST) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == result


def test_drop_preview_lists_retained_assets_without_mutation(monkeypatch, capsys, config) -> None:
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.drop_agent",
        lambda *_: pytest.fail("preview dropped Agent"),
    )

    assert _handle_drop(_args("drop"), config, MANIFEST) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["applied"] is False
    assert "Semantic Views" in payload["retained"]


def test_drop_apply_requires_exact_physical_confirmation(config) -> None:
    with pytest.raises(ValueError, match="--confirm-agent DB.AGENTS.FINANCE_ASSISTANT"):
        _handle_drop(_args("drop", apply=True, confirm_agent="DB.AGENTS.WRONG"), config, MANIFEST)


@pytest.mark.parametrize("existed", [True, False])
def test_drop_apply_distinguishes_newly_dropped_from_already_absent(
    existed, monkeypatch, capsys, config
) -> None:
    result = {"dropped": existed, "before": {"exists": existed}, "after": {"exists": False}}
    calls = []

    def drop(current_config, name, expected_agent_fqn):
        calls.append((name, expected_agent_fqn))
        return result

    monkeypatch.setattr("dbt_cortex_agent.commands.agent.drop_agent", drop)

    assert (
        _handle_drop(
            _args("drop", apply=True, confirm_agent=AGENT["physical_fqn"]),
            config,
            MANIFEST,
        )
        == 0
    )

    assert json.loads(capsys.readouterr().out)["result"]["dropped"] is existed
    assert calls == [(AGENT["name"], AGENT["physical_fqn"])]


def test_deploy_failure_preserves_completed_phase_evidence(monkeypatch, capsys, config) -> None:
    plan = argparse.Namespace(
        agents=(AGENT,),
        skill_uploads=(),
        dbt_selection=("+finance_assistant",),
        resource_databases=("DB",),
    )
    outcome = (
        OperationOutcome()
        .complete(LifecyclePhase.PREFLIGHT)
        .complete(LifecyclePhase.SKILLS_UPLOADED)
        .fail(LifecyclePhase.VERIFIED, "Agent reconciliation phase is indeterminate: dbt failed")
    )
    monkeypatch.setattr("dbt_cortex_agent.commands.agent.build_deploy_plan", lambda *_: plan)
    monkeypatch.setattr("dbt_cortex_agent.commands.agent.validate_deploy_plan", lambda *_: None)
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.apply_deploy_plan",
        lambda *_: (_ for _ in ()).throw(DurablePhaseError("dbt failed", outcome)),
    )

    assert _handle_deploy(_args("deploy", apply=True), config, MANIFEST) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "partial_failure"
    assert [phase["phase"] for phase in payload["phases"]] == [
        "preflight",
        "skills_uploaded",
        "verified",
    ]


def test_drop_partial_failure_retains_evidence_and_exits_two(monkeypatch, capsys, config):
    result = {
        "agent_fqn": AGENT["physical_fqn"],
        "status": "partial_failure",
        "drop_status": "completed",
        "dropped": True,
        "before": {"exists": True},
        "after": None,
        "error": "inspection unavailable",
    }
    monkeypatch.setattr("dbt_cortex_agent.commands.agent.drop_agent", lambda *_: result)
    assert (
        _handle_drop(
            _args("drop", apply=True, confirm_agent=AGENT["physical_fqn"]), config, MANIFEST
        )
        == 2
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == result
    assert "Semantic Views" in payload["retained"]


def test_smoke_expected_tool_failure_preserves_response_and_exit_two(
    monkeypatch, capsys, config
) -> None:
    response = {
        "answer": "I answered without the expected tool.",
        "tool_uses": [{"name": "OtherTool"}],
        "metadata": {},
    }
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.invoke_agent", lambda *args, **kwargs: response
    )

    args = _args(
        "smoke",
        agent="finance_assistant",
        question="Use FinanceTool",
        expect_tool="FinanceTool",
        agent_object=None,
        agent_version=None,
        endpoint=None,
        raw_events=None,
        apply=True,
    )
    assert _handle_smoke(args, config, MANIFEST) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False
    assert payload["response"] == response


def test_smoke_existing_raw_artifact_fails_before_invocation(monkeypatch, config) -> None:
    target = config.artifact_dir / "raw-events" / "smoke.ndjson"
    target.parent.mkdir(parents=True)
    target.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.invoke_agent",
        lambda *args, **kwargs: pytest.fail("Agent invoked before raw-event collision check"),
    )

    args = _args(
        "smoke",
        agent="finance_assistant",
        question="Use FinanceTool",
        expect_tool=None,
        agent_object=None,
        agent_version=None,
        endpoint=None,
        raw_events="smoke.ndjson",
        apply=True,
    )
    with pytest.raises(FileExistsError, match="already exists"):
        _handle_smoke(args, config, MANIFEST)


@pytest.mark.parametrize("json_output", [False, True])
@pytest.mark.parametrize("artifact_written", [False, True])
def test_smoke_runtime_error_retains_partial_response_and_real_artifact(
    monkeypatch,
    capsys,
    config,
    json_output,
    artifact_written,
):
    from dbt_cortex_agent.invoke import AgentInvocationError

    response = {"answer": "partial", "tool_uses": [], "errors": ["stream failed"], "metadata": {}}
    failure = AgentInvocationError("stream failed", response)
    artifact = config.artifact_dir / "raw-events" / "events.jsonl"
    if artifact_written:
        failure.raw_event_path = artifact
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.invoke_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
    )
    args = _args(
        "smoke",
        question="question",
        expect_tool=None,
        agent_object=None,
        agent_version=None,
        endpoint=None,
        raw_events="events.jsonl",
        apply=True,
        json=json_output,
    )
    assert _handle_smoke(args, config, MANIFEST) == 2
    output = capsys.readouterr().out
    if json_output:
        payload = json.loads(output)
        assert payload["response"] == response
        assert payload["passed"] is False
        assert payload["raw_event_artifact"] == (str(artifact) if artifact_written else None)
    else:
        assert "FAIL" in output and "partial" in output
        assert "stream failed" in output
