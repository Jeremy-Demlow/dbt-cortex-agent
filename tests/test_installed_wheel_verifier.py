import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from dbt_cortex_agent.manifest import cortex_agents

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_installed_wheel.py"
SPEC = importlib.util.spec_from_file_location("verify_installed_wheel", SCRIPT)
verifier = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = verifier
SPEC.loader.exec_module(verifier)


def _payloads(fqn=verifier.EXPECTED_AGENT_FQN):
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


def _evidence(tmp_path, *, include_eval, fqn=verifier.EXPECTED_AGENT_FQN):
    _, render_item, doctor = _payloads(fqn)
    if include_eval:
        doctor["diagnostics"][0]["detail"] = "orders_assistant_core"
    return verifier.ProjectEvidence(
        "with-eval" if include_eval else "agent-only",
        tmp_path,
        doctor,
        {"agents": ["orders_assistant"]},
        render_item,
        {
            "applied": False,
            "agent_object": fqn.split(".")[-1],
            "response": None,
            "passed": None,
        },
        (
            {
                "applied": False,
                "passed": None,
                "outcome": "planned",
                "suites": [{"agent_fqn": fqn, "suite": "core"}],
            }
            if include_eval
            else None
        ),
        "dbt_cortex_agent.cortex_eval__execution_plan" if include_eval else "",
        "digest",
        "digest",
        {
            "applied": False,
            "dbt_selection": [f"+{verifier.AGENT}"],
            "agents": [{"physical_fqn": fqn}],
        },
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
    assert (
        "cortex_agent_allowed_databases: [WHEEL_VERIFY_DB]"
        in (optional_eval / "dbt_project.yml").read_text()
    )


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
        (lambda item: item.compiled_agent.update(projection="native_eval"), "projection"),
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


def test_expected_failure_requires_nonzero_exit_and_guidance(tmp_path):
    verifier.run_expected_failure(
        [str(Path(sys.executable)), "-c", "print('use dbt build'); raise SystemExit(2)"],
        cwd=tmp_path,
        env=dict(os.environ),
        expected="use dbt build",
    )
    with pytest.raises(AssertionError, match="expected guidance"):
        verifier.run_expected_failure(
            [str(Path(sys.executable)), "-c", "print('ok')"],
            cwd=tmp_path,
            env=dict(os.environ),
            expected="use dbt build",
        )


def test_run_checked_reports_command_failure(tmp_path):
    with pytest.raises(RuntimeError, match=r"command failed \(7\)"):
        verifier.run_checked(
            [str(Path(sys.executable)), "-c", "raise SystemExit(7)"],
            cwd=tmp_path,
            env=dict(os.environ),
        )


@pytest.mark.parametrize("drift", ["database", "schema", "deploy"])
def test_consumer_validation_rejects_full_identity_drift(tmp_path, drift):
    evidence = _evidence(tmp_path, include_eval=True)
    if drift == "deploy":
        evidence.deploy["agents"][0]["physical_fqn"] = "WRONG.AGENTS.ORDERS_ASSISTANT_SANDBOX"
    else:
        parts = evidence.compiled_agent["physical_agent"].split(".")
        parts[0 if drift == "database" else 1] = "WRONG"
        evidence.compiled_agent["physical_agent"] = ".".join(parts)
    with pytest.raises(AssertionError, match="FQN drift"):
        verifier.validate_project_evidence(evidence, include_eval=True)


def test_default_schema_consumer_parse_and_materialization(tmp_path, macro_harness):
    dbt = shutil.which("dbt")
    if dbt is None:
        pytest.skip("existing dbt executable required; no install attempted")
    project = tmp_path / "consumer"
    package = project / "dbt_packages/dbt_cortex_agent"
    verifier.create_consumer_project(project, package, include_eval=False)
    verifier._copy_dbt_package(ROOT, package)
    (project / "packages.yml").write_text("packages:\n  - local: dbt_packages/dbt_cortex_agent\n")
    models = project / "models"
    models.mkdir()
    (models / "orders_assistant.sql").write_text(
        "{{ config(materialized='cortex_agent', schema='AGENTS', "
        "alias='ORDERS_ASSISTANT_SANDBOX') }}\nmodels:\n  orchestration: test-model\n"
    )
    environment = {
        **os.environ,
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        "DBT_PARTIAL_PARSE": "false",
    }
    verifier.run_checked(
        [
            dbt,
            "parse",
            "--project-dir",
            str(project),
            "--profiles-dir",
            str(project),
            "--target",
            "sandbox",
            "--target-path",
            str(project / "target"),
            "--no-partial-parse",
        ],
        cwd=project,
        env=environment,
    )
    manifest = json.loads((project / "target/manifest.json").read_text())
    agent = cortex_agents(manifest)[0]
    assert agent["physical_fqn"] == verifier.EXPECTED_AGENT_FQN
    node = manifest["nodes"][agent["unique_id"]]
    assert node["config"]["schema"] == "AGENTS"
    assert node["schema"] == "ANALYTICS_AGENTS"
    deployed = []
    statements = []

    def statement(name, caller):
        statements.append(caller().strip())
        return ""

    macro_harness.context.update(
        this=SimpleNamespace(
            database=node["database"], schema=node["schema"], identifier=node["alias"]
        ),
        config=node["config"],
        target=SimpleNamespace(name="sandbox"),
        model=SimpleNamespace(name=node["name"]),
        sql="models:\n  orchestration: test-model\n",
        pre_hooks=[],
        post_hooks=[],
        run_hooks=lambda *args, **kwargs: "",
        statement=statement,
        var=lambda name, default=None: {
            "cortex_agent_allowed_targets": ["sandbox"],
            "cortex_agent_allowed_databases": [verifier.DATABASE],
        }.get(name, default),
    )
    macro_harness.override("cortex_agent__assert_staged_skills_ready", lambda spec: None)
    macro_harness.override("cortex_agent__skills_hash", lambda spec: "hash")
    macro_harness.override("cortex_agent__apply_deploy", lambda *args: deployed.append(args))
    assert macro_harness.call("materialization_cortex_agent") == {"relations": []}
    assert deployed[0][0] == verifier.EXPECTED_AGENT_FQN
    assert len(statements) == 2
    assert all(
        statement.startswith(f"ALTER AGENT {verifier.EXPECTED_AGENT_FQN} SET ")
        for statement in statements
    )
