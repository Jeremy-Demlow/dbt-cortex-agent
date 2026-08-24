from __future__ import annotations

import importlib.util
import json
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
        project_dir=ROOT / "integration_tests", wheel=wheel, connection="live-ci",
        target="sandbox", database_a="LIVE_A", database_b="LIVE_B",
        eval_database="LIVE_EVAL", role="LIVE_ROLE", warehouse="LIVE_WH",
        artifact_dir=tmp_path / "proof",
    )


def test_preview_is_non_mutating_and_writes_sanitized_attestation(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(verifier, "_run", lambda command, **kwargs: calls.append((command, kwargs)))

    output = verifier.run(_config(tmp_path), apply=False, cleanup=False)

    assert calls
    assert all(call[1]["apply"] is False for call in calls)
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
    assert "live_orders_a" in combined
    assert "live_orders_b" in combined
    assert combined.count("dbt build") == 2
    assert "eval run" in combined
    assert "--agent live_orders_a --suite core" in combined
    assert "+live_orders_a +live_orders_b live_orders_a_core" in combined
    assert "--apply" in combined
    assert "eval run --apply" not in combined


def test_invalid_or_colliding_databases_fail_before_commands(tmp_path, monkeypatch):
    config = _config(tmp_path)
    calls = []
    monkeypatch.setattr(verifier, "_run", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(ValueError, match="three distinct"):
        verifier.run(
            verifier.LiveConfig(**{**config.__dict__, "database_b": "LIVE_A"}),
            apply=True, cleanup=True,
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
    states = iter(
        [
            {"agent_fqn": "LIVE_A.AGENTS.SHARED_ASSISTANT", "versions": ["v1"], "aliases": {"DEFAULT": "v1"}},
            {"agent_fqn": "LIVE_B.AGENTS.SHARED_ASSISTANT", "versions": ["v1"], "aliases": {"DEFAULT": "v1"}},
            {"agent_fqn": "LIVE_A.AGENTS.SHARED_ASSISTANT", "versions": ["v1"], "aliases": {"DEFAULT": "v1"}},
            {"agent_fqn": "LIVE_B.AGENTS.SHARED_ASSISTANT", "versions": ["v2"], "aliases": {"DEFAULT": "v2"}},
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