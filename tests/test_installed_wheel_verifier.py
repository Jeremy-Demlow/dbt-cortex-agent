import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_installed_wheel.py"
SPEC = importlib.util.spec_from_file_location("verify_installed_wheel", SCRIPT)
verifier = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = verifier
SPEC.loader.exec_module(verifier)


def _payloads(fqn="WHEEL_VERIFY_DB.AGENTS.ORDERS_ASSISTANT_SANDBOX"):
    spec = {"models": {"orchestration": "claude-sonnet-4-5"}, "tools": []}
    render_item = {
        "agent": "orders_assistant",
        "physical_agent": fqn,
        "lifecycle_contract": "single_agent",
        "target": "sandbox",
        "spec": spec,
    }
    doctor = {
        "passed": True,
        "diagnostics": [{"name": "enabled evals", "status": "PASS", "detail": "none"}],
    }
    return spec, render_item, doctor


def _evidence(tmp_path, *, include_eval, fqn="WHEEL_VERIFY_DB.AGENTS.ORDERS_ASSISTANT_SANDBOX"):
    _, render_item, doctor = _payloads(fqn)
    if include_eval:
        doctor["diagnostics"][0]["detail"] = "orders_assistant_core"
    return verifier.ProjectEvidence(
        "with-eval" if include_eval else "agent-only",
        tmp_path,
        doctor,
        {"agents": ["orders_assistant"]},
        {"renders": [render_item]},
        {"applied": False, "renders": [render_item]},
        {
            "applied": False,
            "agent_object": fqn.split(".")[-1],
            "response": None,
            "passed": None,
        },
        (
            {
                "candidate": None,
                "plan": {"agent_object": fqn, "paid_apply": False},
            }
            if include_eval
            else None
        ),
        "dbt_cortex_agent.cortex_eval__execution_plan" if include_eval else "",
        "digest",
        "digest",
    )


def test_create_consumer_project_is_isolated_and_eval_optional(tmp_path):
    package = tmp_path / "dbt_cortex_agent"
    package.mkdir()
    agent_only = tmp_path / "agent-only"
    optional_eval = tmp_path / "optional-eval"
    verifier.create_consumer_project(agent_only, package, include_eval=False)
    verifier.create_consumer_project(optional_eval, package, include_eval=True)

    assert str(ROOT) not in (agent_only / "packages.yml").read_text()
    assert "../dbt_cortex_agent" in (agent_only / "packages.yml").read_text()
    assert not any((agent_only / path).exists() for path in verifier.EVAL_FILES)
    assert "cortex_agent_allowed_databases: [WHEEL_VERIFY_DB]" in (
        optional_eval / "dbt_project.yml"
    ).read_text()


def test_validate_pair_proves_same_agent_and_optional_eval(tmp_path):
    result = verifier.validate_pair(
        _evidence(tmp_path, include_eval=False),
        _evidence(tmp_path, include_eval=True),
    )
    assert result["passed"] is True
    assert result["projects"]["agent_only"]["eval_action_required"] is False
    assert result["projects"]["agent_plus_optional_eval"]["eval_deployed_agent"] is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda item: item.render["renders"][0].update(projection="native_eval"), "projection"),
        (lambda item: item.smoke.update(agent_object="OTHER"), "FQN drift"),
        (
            lambda item: object.__setattr__(
                item,
                "eval_log",
                "dbt_cortex_agent.cortex_eval__execution_plan cortex_agent__deploy",
            ),
            "lifecycle",
        ),
        (lambda item: object.__setattr__(item, "render_digest_after_eval", "changed"), "changed"),
    ],
)
def test_optional_eval_validation_fails_closed(tmp_path, mutation, message):
    evidence = _evidence(tmp_path, include_eval=True)
    mutation(evidence)
    with pytest.raises(AssertionError, match=message):
        verifier.validate_project_evidence(evidence, include_eval=True)


def test_agent_only_rejects_eval_action(tmp_path):
    evidence = _evidence(tmp_path, include_eval=False)
    object.__setattr__(evidence, "eval_log", "dbt_cortex_agent.cortex_eval__execution_plan")
    with pytest.raises(AssertionError, match="eval action"):
        verifier.validate_project_evidence(evidence, include_eval=False)


@pytest.mark.parametrize(
    "command",
    (
        ["dbt-cortex-agent", "eval", "run", "--apply"],
        ["python", "helper.py", "init", "--apply"],
        ["snow", "connection", "list"],
    ),
)
def test_run_checked_rejects_unsafe_commands_before_execution(tmp_path, command):
    with pytest.raises(ValueError, match="unsafe verifier command"):
        verifier.run_checked(command, cwd=tmp_path, env={})


def test_run_checked_allows_only_cli_init_apply(tmp_path):
    result = verifier.run_checked(
        [str(Path(sys.executable)), "-c", "print('ok')"],
        cwd=tmp_path,
        env=dict(os.environ),
    )
    assert result.stdout.strip() == "ok"


def test_run_checked_reports_command_failure(tmp_path):
    with pytest.raises(RuntimeError, match=r"command failed \(7\)"):
        verifier.run_checked(
            [str(Path(sys.executable)), "-c", "raise SystemExit(7)"],
            cwd=tmp_path,
            env=dict(os.environ),
        )