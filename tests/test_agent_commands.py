from __future__ import annotations

import argparse
import json

import pytest

# Evidence: TC-026-01 TC-026-02 TC-026-03 TC-026-05 TC-026-06 TC-026-09
from dbt_cortex_agent.commands.agent import (
    _handle_deploy,
    _handle_drop,
    _handle_route,
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
    monkeypatch.setattr("dbt_cortex_agent.commands.agent.drop_agent", lambda *_: result)

    assert (
        _handle_drop(
            _args("drop", apply=True, confirm_agent=AGENT["physical_fqn"]),
            config,
            MANIFEST,
        )
        == 0
    )

    assert json.loads(capsys.readouterr().out)["result"]["dropped"] is existed


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
