from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "verify_live_multi_database", ROOT / "scripts/verify_live_multi_database.py"
)
verifier = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verifier
spec.loader.exec_module(verifier)


def _config(tmp_path):
    wheel = tmp_path / "package.whl"
    wheel.write_bytes(b"wheel")
    return verifier.LiveConfig(
        project_dir=ROOT / "integration_tests",
        wheel=wheel,
        connection="live-ci",
        target="sandbox",
        database_a="LIVE_A",
        database_b="LIVE_B",
        eval_database="LIVE_EVAL",
        role="LIVE_ROLE",
        warehouse="LIVE_WH",
        artifact_dir=tmp_path / "proof",
    )


def test_preview_is_non_mutating_and_writes_sanitized_attestation(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(verifier, "_run", lambda command, **kwargs: calls.append((command, kwargs)))

    output = verifier.run(_config(tmp_path), apply=False, cleanup=False)

    assert calls
    assert all(call[1]["apply"] is False for call in calls)
    assert all(call[1]["capture"] is False for call in calls)
    attestation = json.loads(output.read_text())
    assert attestation["status"] == "planned"
    assert attestation["paid_evaluation"] is False
    assert attestation["agents"] == [
        {"agent_fqn": "LIVE_A.AGENTS.SHARED_ASSISTANT"},
        {"agent_fqn": "LIVE_B.AGENTS.SHARED_ASSISTANT"},
    ]
    assert "connection" not in attestation
    assert "account" not in attestation


def test_plan_uses_exact_wheel_and_covers_both_agents(tmp_path):
    config = _config(tmp_path)
    planned = verifier.commands(config, config.artifact_dir / "venv/bin/python")
    combined = "\n".join(" ".join(command) for command in planned)

    assert str(config.wheel) in combined
    assert "dbt-core==1.11.11 dbt-snowflake==1.11.4" in combined
    assert "live_orders_a" in combined
    assert "live_orders_b" in combined
    assert combined.count("agent deploy") == 2
    assert "skill plan" not in combined
    assert "eval verify" in combined
    assert "--agent live_orders_a --suite core" in combined
    assert "--agent live_orders_a --agent live_orders_b" in combined
    assert "--allow-database LIVE_A --allow-database LIVE_B --allow-database LIVE_EVAL" in combined
    assert "--apply" in combined
    assert "eval verify --apply" not in combined


def test_lifecycle_plan_covers_v2_promotion_rollback_rollforward_and_drop(tmp_path):
    config = _config(tmp_path)
    python = config.artifact_dir / "venv/bin/python"
    lifecycle = "\n".join(
        " ".join(command) for command in verifier.lifecycle_commands(config, python)
    )
    drops = "\n".join(
        " ".join(command) for command in verifier.guarded_drop_commands(config, python)
    )

    assert "agent deploy" in lifecycle
    assert "--version VERSION$2" in lifecycle
    assert "agent promote" in lifecycle
    assert "agent rollback" in lifecycle
    assert "--to-version VERSION$1" in lifecycle
    assert lifecycle.count("agent promote") == 3
    assert "agent versions" in lifecycle
    assert "agent drop" in drops
    assert "--confirm-agent LIVE_A.AGENTS.SHARED_ASSISTANT" in drops
    assert "--confirm-agent LIVE_B.AGENTS.SHARED_ASSISTANT" in drops


def test_invalid_or_colliding_databases_fail_before_commands(tmp_path, monkeypatch):
    config = _config(tmp_path)
    calls = []
    monkeypatch.setattr(verifier, "_run", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(ValueError, match="three distinct"):
        verifier.run(
            verifier.LiveConfig(**{**config.__dict__, "database_b": "LIVE_A"}),
            apply=True,
            cleanup=True,
        )
    assert calls == []


def test_cleanup_is_bounded_to_proof_objects(tmp_path):
    combined = "\n".join(
        " ".join(command) for command in verifier.cleanup_commands(_config(tmp_path))
    )

    assert "DROP DATABASE" not in combined
    assert "LIVE_A.AGENTS.SHARED_ASSISTANT" in combined
    assert "LIVE_B.AGENTS.SHARED_ASSISTANT" in combined
    assert "LIVE_EVAL.EVAL.LIVE_ORDERS_A_CORE" in combined


def test_no_change_reconciliation_compares_observed_agent_state(tmp_path, monkeypatch):
    monkeypatch.setattr(verifier, "_preflight", lambda *args: None)
    states = iter(
        [
            {
                "agent_fqn": "LIVE_A.AGENTS.SHARED_ASSISTANT",
                "versions": ["v1"],
                "aliases": {"DEFAULT": "v1"},
            },
            {
                "agent_fqn": "LIVE_B.AGENTS.SHARED_ASSISTANT",
                "versions": ["v1"],
                "aliases": {"DEFAULT": "v1"},
            },
            {
                "agent_fqn": "LIVE_A.AGENTS.SHARED_ASSISTANT",
                "versions": ["v1"],
                "aliases": {"DEFAULT": "v1"},
            },
            {
                "agent_fqn": "LIVE_B.AGENTS.SHARED_ASSISTANT",
                "versions": ["v2"],
                "aliases": {"DEFAULT": "v2"},
            },
        ]
    )
    monkeypatch.setattr(verifier, "_run", lambda *args, **kwargs: "")
    monkeypatch.setattr(verifier, "_agent_state", lambda *args, **kwargs: next(states))

    with pytest.raises(RuntimeError, match="No-change reconciliation"):
        verifier.run(_config(tmp_path), apply=True, cleanup=False)


def test_isolated_venv_is_added_to_subprocess_path(tmp_path, monkeypatch):
    paths = []

    def capture_run(command, **kwargs):
        paths.append(kwargs["env"]["PATH"])
        return ""

    monkeypatch.setattr(verifier, "_run", capture_run)

    verifier.run(_config(tmp_path), apply=False, cleanup=False)

    assert paths
    assert all(path.startswith(str(_config(tmp_path).artifact_dir / "venv/bin")) for path in paths)


def test_applied_proof_recreates_isolated_venv(tmp_path, monkeypatch):
    _successful_proof(monkeypatch)
    commands = []
    monkeypatch.setattr(
        verifier,
        "_run",
        lambda command, **kwargs: commands.append(command) or "",
    )
    verifier.run(_config(tmp_path), apply=True, cleanup=False)

    assert commands[0][1:4] == ["-m", "venv", "--clear"]


def _successful_proof(monkeypatch):
    monkeypatch.setattr(verifier, "_run", lambda *args, **kwargs: "")
    monkeypatch.setattr(verifier, "_preflight", lambda *args: None)
    monkeypatch.setattr(verifier, "_verify_identity", lambda *args: None)
    monkeypatch.setattr(verifier, "_proof_inventory", lambda *args: [])
    observations = iter(
        [
            (False, "VERSION$1"),
            (False, "VERSION$1"),
            (False, "VERSION$1"),
            (True, "VERSION$1"),
            (True, "VERSION$2"),
            (True, "VERSION$1"),
            (True, "VERSION$1"),
            (True, "VERSION$2"),
            (True, "VERSION$2"),
        ]
    )

    def state(config, database, env):
        changed, version = (
            next(observations) if database == config.database_a else (False, "VERSION$1")
        )
        return {
            "agent_fqn": f"{database}.AGENTS.SHARED_ASSISTANT",
            "versions": ["VERSION$1", "VERSION$2"] if changed else ["VERSION$1"],
            "aliases": {"DEFAULT": version, "PRODUCTION": version},
        }

    monkeypatch.setattr(verifier, "_agent_state", state)


def test_attestation_retains_both_observed_databases_and_cleanup(tmp_path, monkeypatch):
    _successful_proof(monkeypatch)
    output = verifier.run(_config(tmp_path), apply=True, cleanup=True)
    evidence = json.loads(output.read_text())
    assert evidence["schema_version"] == 1
    assert (
        evidence["status"] == evidence["proof_status"] == evidence["cleanup_status"] == "completed"
    )
    assert evidence["guarded_retirement"] is True
    assert evidence["paid_evaluation"] is False
    assert [agent["agent_fqn"] for agent in evidence["agents"]] == [
        "LIVE_A.AGENTS.SHARED_ASSISTANT",
        "LIVE_B.AGENTS.SHARED_ASSISTANT",
    ]
    assert evidence["agents"][0]["versions"] == ["VERSION$1", "VERSION$2"]
    assert evidence["agents"][1]["versions"] == ["VERSION$1"]
    assert evidence["agents"][1]["aliases"]["DEFAULT"] == "VERSION$1"
    assert evidence["reconciliation"]["before"] == evidence["reconciliation"]["after"]
    assert len(evidence["reconciliation"]["before"]) == 2


@pytest.mark.parametrize("phase", ["setup", "observation", "lifecycle", "retirement"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_failed_proof_always_retains_attestation_and_primary(
    tmp_path, monkeypatch, phase, cleanup_fails
):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    primary = RuntimeError("private subprocess output must not enter attestation")

    def run_command(command, **kwargs):
        if (phase == "setup" and "venv" in command) or (
            phase == "retirement" and "drop" in command
        ):
            raise primary
        return ""

    monkeypatch.setattr(verifier, "_run", run_command)
    original = verifier._agent_state
    observed = []

    def state(config, database, env):
        observed.append(database)
        if phase == "observation" and len(observed) == 2:
            raise primary
        if phase == "lifecycle" and len(observed) == 5:
            raise primary
        return original(config, database, env)

    monkeypatch.setattr(verifier, "_agent_state", state)
    cleaned = []

    def cleanup(*args):
        cleaned.append(True)
        if cleanup_fails:
            raise OSError("private cleanup output")

    monkeypatch.setattr(verifier, "_cleanup", cleanup)
    with pytest.raises(RuntimeError) as error:
        verifier.run(config, apply=True, cleanup=True)
    assert error.value is primary
    assert cleaned == [True]
    evidence = json.loads((config.artifact_dir / "live-attestation.json").read_text())
    assert evidence["status"] == evidence["proof_status"] == "failed"
    assert evidence["cleanup_status"] == ("failed" if cleanup_fails else "completed")
    assert evidence["proof_error_type"] == "RuntimeError"
    assert evidence["guarded_retirement"] is False
    assert len(evidence["agents"]) == 2
    if phase == "observation":
        assert evidence["agents"][0]["versions"] == ["VERSION$1"]
        assert "versions" not in evidence["agents"][1]
    assert "private" not in json.dumps(evidence)


@pytest.mark.parametrize("separate", [False, True])
def test_cleanup_failure_cannot_report_completed_run(tmp_path, monkeypatch, separate):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    if separate:
        verifier.run(config, apply=True, cleanup=False)

    def fail(*args):
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(verifier, "_cleanup", fail)
    with pytest.raises(RuntimeError, match="cleanup failed"):
        verifier.run(config, apply=True, cleanup=not separate, cleanup_only=separate)
    evidence = json.loads((config.artifact_dir / "live-attestation.json").read_text())
    assert evidence["status"] == evidence["cleanup_status"] == "failed"
    assert evidence["proof_status"] == "completed"
    assert evidence["cleanup_error_type"] == "RuntimeError"
    assert len(evidence["agents"]) == 2


def test_cleanup_only_preserves_failed_proof_and_retries_cleanup(tmp_path, monkeypatch):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)

    def fail(*args, **kwargs):
        raise RuntimeError("proof failed")

    with monkeypatch.context() as failed:
        failed.setattr(verifier, "_assert_lifecycle_state", fail)
        failed.setattr(verifier, "_cleanup", fail)
        with pytest.raises(RuntimeError):
            verifier.run(config, apply=True, cleanup=True)
    path = config.artifact_dir / "live-attestation.json"
    before = json.loads(path.read_text())
    verifier.run(config, apply=True, cleanup=False, cleanup_only=True)
    after = json.loads(path.read_text())
    assert after["status"] == after["proof_status"] == "failed"
    assert after["cleanup_status"] == "completed"
    assert "cleanup_error_type" not in after
    for key in (
        "agents",
        "reconciliation",
        "wheel_sha256",
        "proof_error_type",
        "guarded_retirement",
    ):
        assert after[key] == before[key]


@pytest.mark.parametrize("apply", [False, True])
def test_cleanup_only_without_proof_never_claims_qualification(tmp_path, monkeypatch, apply):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    config.wheel.unlink()
    output = verifier.run(config, apply=apply, cleanup=False, cleanup_only=True)
    evidence = json.loads(output.read_text())
    assert evidence["status"] == evidence["proof_status"] == "not_started"
    assert evidence["cleanup_status"] == ("not_authorized" if apply else "planned")
    assert evidence["wheel_sha256"] is None
    assert evidence["guarded_retirement"] is False


def test_cleanup_only_preview_preserves_existing_evidence(tmp_path, monkeypatch):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    output = verifier.run(config, apply=True, cleanup=True)
    before = output.read_bytes()
    verifier.run(config, apply=False, cleanup=False, cleanup_only=True)
    assert output.read_bytes() == before


def test_cleanup_only_success_preserves_both_observed_states(tmp_path, monkeypatch):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    output = verifier.run(config, apply=True, cleanup=False)
    before = json.loads(output.read_text())
    verifier.run(config, apply=True, cleanup=False, cleanup_only=True)
    after = json.loads(output.read_text())
    assert after["status"] == after["proof_status"] == after["cleanup_status"] == "completed"
    assert after["cleanup_requested"] is True
    for key in ("agents", "reconciliation", "wheel_sha256", "guarded_retirement"):
        assert after[key] == before[key]


@pytest.mark.parametrize("field", ["target", "database_b", "eval_database", "wheel"])
def test_cleanup_only_rejects_mismatched_proof_before_effects(tmp_path, monkeypatch, field):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    output = verifier.run(config, apply=True, cleanup=False)
    before = output.read_bytes()
    if field == "wheel":
        config.wheel.write_bytes(b"different wheel")
    else:
        config = verifier.LiveConfig(**{**config.__dict__, field: "DIFFERENT"})
    calls = []
    monkeypatch.setattr(verifier, "_cleanup", lambda *args: calls.append(args))
    with pytest.raises(ValueError, match="mismatched"):
        verifier.run(config, apply=True, cleanup=False, cleanup_only=True)
    assert calls == []
    assert output.read_bytes() == before


def test_cleanup_attempts_all_objects_after_command_failure(tmp_path, monkeypatch):
    calls = []

    def run_command(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            raise OSError("unavailable")
        return ""

    monkeypatch.setattr(verifier, "_run", run_command)
    config = _config(tmp_path)
    with pytest.raises(RuntimeError, match="Cleanup failed"):
        verifier._cleanup(config, {}, True)
    assert calls == verifier.cleanup_commands(config)


@pytest.mark.parametrize("inherited", [None, "", "/unrelated/bin/dbt"])
@pytest.mark.parametrize("apply", [False, True])
def test_proof_pins_dbt_for_all_phases_despite_inherited_executable(
    tmp_path, monkeypatch, inherited, apply
):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    if inherited is None:
        monkeypatch.delenv("DBT_EXECUTABLE", raising=False)
    else:
        monkeypatch.setenv("DBT_EXECUTABLE", inherited)
    monkeypatch.setenv("PATH", "/unrelated/bin")
    calls = []

    def capture_run(command, **kwargs):
        calls.append((command, kwargs))
        return ""

    monkeypatch.setattr(verifier, "_run", capture_run)
    verifier.run(config, apply=apply, cleanup=True)

    expected = str(config.artifact_dir / "venv/bin/dbt")
    assert calls
    assert all(kwargs["env"]["DBT_EXECUTABLE"] == expected for _, kwargs in calls)
    assert all(
        kwargs["env"]["PATH"] == f"{Path(expected).parent}{os.pathsep}/unrelated/bin"
        for _, kwargs in calls
    )
    assert any(command[0] == expected and command[1] == "deps" for command, _ in calls)
    assert any("promote" in command for command, _ in calls)
    assert [command for command, _ in calls[-4:]] == verifier.cleanup_commands(config)
    if apply:
        assert any("drop" in command for command, _ in calls)
    else:
        assert all(kwargs["apply"] is False for _, kwargs in calls)
    assert os.environ.get("DBT_EXECUTABLE") == inherited
    assert os.environ["PATH"] == "/unrelated/bin"


@pytest.mark.parametrize("prior_proof", [False, True])
def test_cleanup_only_uses_same_pinned_environment_without_venv(tmp_path, monkeypatch, prior_proof):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    if prior_proof:
        verifier.run(config, apply=True, cleanup=False)
    assert not (config.artifact_dir / "venv").exists()
    monkeypatch.setenv("DBT_EXECUTABLE", "/unrelated/bin/dbt")
    calls = []

    def capture_run(command, **kwargs):
        calls.append((command, kwargs))
        return ""

    monkeypatch.setattr(verifier, "_run", capture_run)
    output = verifier.run(config, apply=True, cleanup=False, cleanup_only=True)
    assert [command for command, _ in calls] == (
        verifier.cleanup_commands(config) if prior_proof else []
    )
    assert all(
        kwargs["env"]["DBT_EXECUTABLE"] == str(config.artifact_dir / "venv/bin/dbt")
        for _, kwargs in calls
    )
    evidence = json.loads(output.read_text())
    assert evidence["proof_status"] == ("completed" if prior_proof else "not_started")
    assert evidence["cleanup_status"] == ("completed" if prior_proof else "not_authorized")
    assert os.environ["DBT_EXECUTABLE"] == "/unrelated/bin/dbt"


def test_fake_setup_without_pinned_dbt_fails_instead_of_using_host(tmp_path, monkeypatch):
    real_run = verifier._run
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    expected = str(config.artifact_dir / "venv/bin/dbt")
    monkeypatch.setenv("DBT_EXECUTABLE", sys.executable)
    calls = []

    def fake_setup(command, **kwargs):
        calls.append((command, kwargs))
        if command[0] == expected:
            return real_run(command, **kwargs)
        return ""

    monkeypatch.setattr(verifier, "_run", fake_setup)
    with pytest.raises(FileNotFoundError) as failure:
        verifier.run(config, apply=True, cleanup=True)
    assert failure.value.filename == expected
    assert all(kwargs["env"]["DBT_EXECUTABLE"] == expected for _, kwargs in calls)
    assert [command for command, _ in calls[-4:]] == verifier.cleanup_commands(config)
    evidence = json.loads((config.artifact_dir / "live-attestation.json").read_text())
    assert evidence["status"] == evidence["proof_status"] == "failed"
    assert evidence["proof_error_type"] == "FileNotFoundError"
    assert evidence["cleanup_status"] == "completed"


def test_same_value_pin_precedes_candidate_and_retains_native_postcondition(tmp_path, monkeypatch):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    calls = []
    monkeypatch.setattr(
        verifier, "_run", lambda command, **kwargs: calls.append((command, kwargs)) or ""
    )
    output = verifier.run(config, apply=True, cleanup=False)
    phases = [
        (command, kwargs["env"]["CORTEX_AGENT_LIVE_SPEC_REVISION"])
        for command, kwargs in calls
        if "promote" in command or "deploy" in command
    ]
    pin = next(index for index, (command, _) in enumerate(phases) if "promote" in command)
    assert phases[pin][1] == "v1"
    assert phases[pin][0][phases[pin][0].index("--version") + 1] == "VERSION$1"
    assert "deploy" in phases[pin + 1][0] and phases[pin + 1][1] == "v2"
    regression = json.loads(output.read_text())["default_pin_regression"]
    assert regression["pinned"]["versions"] == ["VERSION$1"]
    assert regression["after_candidate_commit"]["versions"] == ["VERSION$1", "VERSION$2"]
    assert regression["after_candidate_commit"]["aliases"]["DEFAULT"] == "VERSION$1"
    assert regression["rolled_forward"]["aliases"]["PRODUCTION"] == "VERSION$2"


@pytest.mark.parametrize("failure", ["default_drift", "production_drift", "missing_version"])
def test_later_commit_failure_blocks_promotion_and_preserves_failure(
    tmp_path, monkeypatch, failure
):
    _successful_proof(monkeypatch)
    original = verifier._agent_state
    observed_a = 0
    calls = []

    def state(config, database, env):
        nonlocal observed_a
        result = original(config, database, env)
        if database == config.database_a:
            observed_a += 1
        if database == config.database_a and observed_a == 4:
            if failure == "missing_version":
                result["versions"] = ["VERSION$1"]
            else:
                key = "DEFAULT" if failure == "default_drift" else "PRODUCTION"
                result["aliases"][key] = "VERSION$2"
        return result

    monkeypatch.setattr(verifier, "_agent_state", state)
    monkeypatch.setattr(verifier, "_run", lambda command, **kwargs: calls.append(command) or "")
    config = _config(tmp_path)
    with pytest.raises(RuntimeError, match="postcondition"):
        verifier.run(config, apply=True, cleanup=True)
    assert sum("promote" in command for command in calls) == 1
    evidence = json.loads((config.artifact_dir / "live-attestation.json").read_text())
    assert evidence["proof_status"] == evidence["status"] == "failed"
    assert evidence["cleanup_status"] == "completed"
    observed = evidence["default_pin_regression"]["after_candidate_commit"]
    assert observed == evidence["agents"][0]
    if failure == "missing_version":
        assert observed["versions"] == ["VERSION$1"]
    else:
        key = "DEFAULT" if failure == "default_drift" else "PRODUCTION"
        assert observed["aliases"][key] == "VERSION$2"


@pytest.mark.parametrize(
    "field", ["ORGANIZATION_NAME", "ACCOUNT_NAME", "ROLE_NAME", "DATABASE_NAME", "WAREHOUSE_NAME"]
)
def test_identity_mismatch_refuses_before_effects(tmp_path, monkeypatch, field):
    config = _config(tmp_path)
    row = {
        "ORGANIZATION_NAME": config.expected_organization,
        "ACCOUNT_NAME": config.expected_account,
        "ROLE_NAME": config.role,
        "DATABASE_NAME": config.database_a,
        "WAREHOUSE_NAME": config.warehouse,
    }
    row[field] = "WRONG"
    monkeypatch.setattr(verifier, "_rows", lambda *args: [row])
    with pytest.raises(RuntimeError, match="identity mismatch"):
        verifier._preflight(config, {})


def test_preflight_collision_never_authorizes_cleanup(tmp_path, monkeypatch):
    config = _config(tmp_path)
    calls = []
    monkeypatch.setattr(verifier, "_verify_identity", lambda *args: None)
    monkeypatch.setattr(
        verifier, "_proof_inventory", lambda *args: ["LIVE_A.AGENTS.SHARED_ASSISTANT"]
    )
    monkeypatch.setattr(verifier, "_run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(RuntimeError, match="already exist"):
        verifier.run(config, apply=True, cleanup=True)
    assert calls == []
    evidence = json.loads((config.artifact_dir / "live-attestation.json").read_text())
    assert evidence["cleanup_authorized"] is False
    assert evidence["cleanup_status"] == "not_authorized"


def test_local_timeout_is_unknown_server_state(tmp_path, monkeypatch):
    import subprocess

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 600
        raise subprocess.TimeoutExpired(args[0], 600)

    monkeypatch.setattr(verifier.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="server state unknown"):
        verifier._run(["fake"], cwd=tmp_path, env={}, apply=True)


def test_timeout_blocks_automatic_cleanup_and_cleanup_only(tmp_path, monkeypatch):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    cleanup = []
    monkeypatch.setattr(verifier, "_cleanup", lambda *args: cleanup.append(args))

    def timeout(command, **kwargs):
        if "deploy" in command:
            raise verifier.UnknownServerState("Local timeout; server state unknown")
        return ""

    monkeypatch.setattr(verifier, "_run", timeout)
    with pytest.raises(verifier.UnknownServerState):
        verifier.run(config, apply=True, cleanup=True)
    verifier.run(config, apply=True, cleanup=False, cleanup_only=True)
    assert cleanup == []
    evidence = json.loads((config.artifact_dir / "live-attestation.json").read_text())
    assert evidence["server_state_unknown"] is True
    assert evidence["cleanup_status"] == "not_authorized"
    assert evidence["proof_status"] == "failed"


def test_proof_refuses_existing_evidence_before_commands(tmp_path, monkeypatch):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    output = verifier.run(config, apply=False, cleanup=False)
    before = output.read_bytes()
    calls = []
    monkeypatch.setattr(verifier, "_run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError, match="already exists"):
        verifier.run(config, apply=True, cleanup=True)
    assert calls == [] and output.read_bytes() == before


def test_pin_write_failure_cannot_qualify_or_start_candidate(tmp_path, monkeypatch):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    calls = []

    def failure(command, **kwargs):
        calls.append(command)
        if "promote" in command:
            raise RuntimeError("DEFAULT pin write failed")
        return ""

    monkeypatch.setattr(verifier, "_run", failure)
    with pytest.raises(RuntimeError, match="pin write failed"):
        verifier.run(config, apply=True, cleanup=True)
    assert sum("deploy" in command for command in calls) == 2
    evidence = json.loads((config.artifact_dir / "live-attestation.json").read_text())
    assert evidence["proof_status"] == "failed" and evidence["cleanup_status"] == "completed"


def test_existing_seed_must_match_exact_reviewed_fixture(tmp_path, monkeypatch):
    config = _config(tmp_path)
    monkeypatch.setattr(verifier, "_verify_identity", lambda *args: None)
    monkeypatch.setattr(verifier, "_proof_inventory", lambda *args: [])
    responses = iter(
        [
            [{"NAME": "ORDERS"}],
            [{"ORDER_ID": 1, "ORDER_DATE": "2026-01-05", "REGION": "North", "REVENUE": 120.50}],
        ]
    )
    monkeypatch.setattr(verifier, "_rows", lambda *args: next(responses))
    with pytest.raises(RuntimeError, match="seed differs"):
        verifier._preflight(config, {})


@pytest.mark.parametrize("phase", ["identity", "drop", "inventory"])
def test_cleanup_timeout_stops_and_blocks_retries(tmp_path, monkeypatch, phase):
    _successful_proof(monkeypatch)
    config = _config(tmp_path)
    verifier.run(config, apply=True, cleanup=False)
    drops = []

    def timeout(*args, **kwargs):
        raise verifier.UnknownServerState("server state unknown")

    def run(command, **kwargs):
        drops.append(command)
        raise verifier.UnknownServerState("server state unknown")

    if phase == "identity":
        monkeypatch.setattr(verifier, "_verify_identity", timeout)
    elif phase == "inventory":
        monkeypatch.setattr(verifier, "_proof_inventory", timeout)
    else:
        monkeypatch.setattr(verifier, "_run", run)
    with pytest.raises(verifier.UnknownServerState):
        verifier.run(config, apply=True, cleanup=False, cleanup_only=True)
    assert len(drops) == (1 if phase == "drop" else 0)
    verifier.run(config, apply=True, cleanup=False, cleanup_only=True)
    assert len(drops) == (1 if phase == "drop" else 0)
    evidence = json.loads((config.artifact_dir / "live-attestation.json").read_text())
    assert evidence["server_state_unknown"] is True
    assert evidence["cleanup_status"] == "not_authorized"
    assert evidence["status"] == "failed"
    assert evidence["cleanup_error_type"] == "UnknownServerState"


def test_command_driven_implicit_default_model(tmp_path, monkeypatch):
    import copy

    config = _config(tmp_path)
    states = {
        database: {
            "agent_fqn": f"{database}.AGENTS.SHARED_ASSISTANT",
            "versions": [],
            "aliases": {},
        }
        for database in (config.database_a, config.database_b)
    }
    explicit = False
    monkeypatch.setattr(verifier, "_preflight", lambda *args: None)
    monkeypatch.setattr(verifier, "_verify_identity", lambda *args: None)
    monkeypatch.setattr(verifier, "_proof_inventory", lambda *args: [])
    monkeypatch.setattr(
        verifier, "_agent_state", lambda config, database, env: copy.deepcopy(states[database])
    )

    def execute(command, **kwargs):
        nonlocal explicit
        if "deploy" in command:
            selected = [
                command[index + 1] for index, item in enumerate(command) if item == "--agent"
            ]
            for agent in selected:
                database = config.database_a if agent == "live_orders_a" else config.database_b
                state = states[database]
                candidate = (
                    "VERSION$2"
                    if kwargs["env"]["CORTEX_AGENT_LIVE_SPEC_REVISION"] == "v2"
                    else "VERSION$1"
                )
                if candidate not in state["versions"]:
                    state["versions"].append(candidate)
                state["aliases"]["LATEST"] = candidate
                if database != config.database_a or not explicit:
                    state["aliases"]["DEFAULT"] = candidate
        elif "promote" in command or "rollback" in command:
            flag = "--version" if "promote" in command else "--to-version"
            routed = command[command.index(flag) + 1]
            states[config.database_a]["aliases"].update(DEFAULT=routed, PRODUCTION=routed)
            explicit = True
        return ""

    monkeypatch.setattr(verifier, "_run", execute)
    output = verifier.run(config, apply=True, cleanup=True)
    evidence = json.loads(output.read_text())
    assert evidence["proof_status"] == "completed"
    assert "PRODUCTION" not in evidence["reconciliation"]["before"][0]["aliases"]
    assert (
        evidence["default_pin_regression"]["after_candidate_commit"]["aliases"]["DEFAULT"]
        == "VERSION$1"
    )


@pytest.mark.parametrize("aliases", [None, "{}", "not json"])
def test_native_inspection_rejects_incomplete_or_malformed_aliases(tmp_path, monkeypatch, aliases):
    config = _config(tmp_path)
    rows = iter([[{"NAME": "VERSION$1"}], [{"ALIASES": aliases}]])
    monkeypatch.setattr(verifier, "_rows", lambda *args: next(rows))
    with pytest.raises((RuntimeError, ValueError)):
        verifier._agent_state(config, config.database_a, {})


def test_native_rows_normalize_lowercase_keys_and_exclude_live(tmp_path, monkeypatch):
    config = _config(tmp_path)
    responses = iter(
        [
            json.dumps([{"name": "LIVE"}, {"name": "VERSION$2"}, {"name": "VERSION$1"}]),
            json.dumps([{"aliases": '{"DEFAULT":"VERSION$1","LATEST":"VERSION$2"}'}]),
        ]
    )
    monkeypatch.setattr(verifier, "_run", lambda *args, **kwargs: next(responses))
    state = verifier._agent_state(config, config.database_a, {})
    assert state["versions"] == ["VERSION$1", "VERSION$2"]
    assert state["aliases"] == {"DEFAULT": "VERSION$1", "LATEST": "VERSION$2"}
