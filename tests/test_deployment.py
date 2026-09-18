from __future__ import annotations

import copy
import json
import subprocess
from types import SimpleNamespace

import pytest

# Evidence: TC-022-01 TC-022-05 TC-023-08 TC-030-03 TC-030-04
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.deployment import (
    _dbt_phases,
    apply_deploy_plan,
    build_deploy_plan,
    validate_deploy_plan,
)
from dbt_cortex_agent.domain import DurablePhaseError, LifecyclePhase, OperationOutcome


class Rows(list):
    def __init__(self, columns, rows):
        super().__init__(rows)
        self.column_names = columns
        self.rows = rows


def _deploy_mutation(behavior, sql):
    parts = sql.split()
    assert parts[:2] == ["ALTER", "AGENT"], sql
    agent_fqn = parts[2]
    state = behavior.states[agent_fqn]
    operations = {
        " ADD LIVE ": "live_add",
        " MODIFY LIVE ": "spec",
        " COMMIT ": "commit",
        " SET COMMENT ": "metadata",
        " UNSET ALIAS": "alias_unset",
        " SET ALIAS ": "alias_set",
    }
    phase = next((phase for token, phase in operations.items() if token in sql), None)
    assert phase is not None, f"Unexpected mutation (including role or DEFAULT movement): {sql}"
    if behavior.fault["agent"] == agent_fqn and behavior.fault["phase"] == phase:
        raise RuntimeError(f"controlled {phase} failure")
    behavior.effects.append((agent_fqn, phase, sql))
    if phase == "live_add":
        state["live"] = behavior.fault["phase"] != "live_postcondition"
        state["live_added"] = True
    elif phase == "commit":
        version = f"VERSION${len(state['versions']) + 1}"
        state["versions"][version] = sql.split("$$")[1]
        state["aliases"]["LAST"] = version
        state["live"] = False
        return Rows(["result"], [[f"Committed {version}"]])
    elif phase == "metadata":
        state["versions"][parts[5]] = sql.split("$$")[1]
    elif phase == "alias_unset":
        state["aliases"].pop("SANDBOX")
    elif phase == "alias_set":
        state["aliases"]["SANDBOX"] = parts[5]
    return Rows([], [])


def _deploy_query(behavior, sql):
    if sql.startswith("CREATE AGENT"):
        agent_fqn = sql.split()[2]
        assert agent_fqn not in behavior.states
        behavior.states[agent_fqn] = {
            "versions": {"VERSION$1": ""},
            "aliases": {"DEFAULT": "VERSION$1", "LAST": "VERSION$1"},
            "live": False,
            "comment": "Managed by dbt cortex_agent materialization",
        }
        behavior.effects.append((agent_fqn, "create", sql))
        if behavior.fault["phase"] == "create_ack":
            raise RuntimeError("CREATE acknowledgement lost")
        return Rows([], [])
    if sql.startswith("SHOW AGENTS"):
        database = sql.split()[-1].split(".")[0]
        return Rows(
            ["name"], [["SHARED"]] if f"{database}.AGENTS.SHARED" in behavior.states else []
        )
    if sql.startswith("SHOW VERSIONS"):
        state = behavior.states[sql.split()[-1]]
        if (
            behavior.fault["agent"] == sql.split()[-1]
            and state.get("live_added")
            and behavior.fault["phase"] == "live_verify"
        ):
            raise RuntimeError("LIVE inspection unavailable")
        rows = [[None, name, comment] for name, comment in state["versions"].items()]
        if state["live"]:
            rows.append([None, "", ""])
        return Rows(["created_on", "name", "comment"], rows)
    if sql.startswith("DESCRIBE AGENT"):
        if behavior.fault["phase"] == "create_inspect":
            raise RuntimeError("created Agent inspection unavailable")
        state = behavior.states[sql.split()[-1]]
        return Rows(["aliases", "comment"], [[json.dumps(state["aliases"]), state.get("comment")]])
    return _deploy_mutation(behavior, sql)


@pytest.fixture
def deploy_behavior(macro_harness):

    states = {
        f"{database}.AGENTS.SHARED": {
            "versions": {"VERSION$1": "spec_md5=aa", "VERSION$2": "spec_md5=bb"},
            "aliases": {"DEFAULT": "VERSION$1", "LAST": "VERSION$2", "SANDBOX": "VERSION$1"},
            "live": True,
        }
        for database in ("DB_A", "DB_B")
    }
    effects = []
    logs = []
    fault = {"agent": "DB_A.AGENTS.SHARED", "phase": None}
    behavior = SimpleNamespace(
        harness=macro_harness, states=states, effects=effects, logs=logs, fault=fault
    )

    macro_harness.context.update(
        run_query=lambda sql: _deploy_query(behavior, sql),
        log=lambda message, **kwargs: logs.append(message),
        local_md5=lambda value: "cc",
        target=SimpleNamespace(name="sandbox"),
        invocation_id="synthetic-invocation",
        var=lambda name, default=None: {
            "cortex_agent_allowed_targets": ["sandbox"],
            "cortex_agent_allowed_databases": ["DB_A", "DB_B"],
        }.get(name, default),
    )

    def deploy(agent_fqn="DB_A.AGENTS.SHARED", reconcile_alias=True, skill_hash="", spec_json="{}"):
        return macro_harness.call(
            "cortex_agent__apply_deploy",
            agent_fqn,
            spec_json,
            "SANDBOX",
            reconcile_alias=reconcile_alias,
            skill_hash=skill_hash,
        )

    behavior.deploy = deploy
    return behavior


@pytest.mark.parametrize("skill_hash", ["", "aa"])
def test_absent_agent_creates_one_version_and_retry_reuses_it(deploy_behavior, skill_hash):
    behavior = deploy_behavior
    del behavior.states["DB_A.AGENTS.SHARED"]
    behavior.deploy(skill_hash=skill_hash)
    behavior.deploy(skill_hash=skill_hash)
    state = behavior.states["DB_A.AGENTS.SHARED"]
    assert list(state["versions"]) == ["VERSION$1"]
    assert state["aliases"]["DEFAULT"] == state["aliases"]["SANDBOX"] == "VERSION$1"
    assert state["live"] is True
    assert sum(phase == "create" for _, phase, _ in behavior.effects) == 1
    assert all(phase != "commit" for _, phase, _ in behavior.effects)


@pytest.mark.parametrize("failure", ["create_ack", "create_inspect", "metadata"])
@pytest.mark.parametrize("retry_skill_hash", ["", "aa", "bb"])
@pytest.mark.parametrize("force", [False, True])
def test_post_create_interruption_requires_recovery_without_duplicate(
    deploy_behavior, failure, retry_skill_hash, force
):
    behavior = deploy_behavior
    del behavior.states["DB_A.AGENTS.SHARED"]
    behavior.fault["phase"] = failure
    with pytest.raises(RuntimeError):
        behavior.deploy(skill_hash="aa")
    state = copy.deepcopy(behavior.states)
    effects = list(behavior.effects)
    phases = _dbt_phases("\n".join(behavior.logs), OperationOutcome()).phases
    assert [phase.phase for phase in phases] == (
        [LifecyclePhase.VERSION_COMMITTED] if failure == "metadata" else []
    )
    behavior.fault["phase"] = None
    original_var = behavior.harness.context["var"]
    behavior.harness.context["var"] = lambda name, default=None: (
        force if name == "force_agent_recreate" else original_var(name, default)
    )
    for retry_spec in ["{}", '{"instructions":{"system":"changed"}}']:
        with pytest.raises(ValueError, match="explicit recovery required"):
            behavior.deploy(skill_hash=retry_skill_hash, spec_json=retry_spec)
    assert behavior.states == state
    assert behavior.effects == effects
    assert all(phase != "commit" for _, phase, _ in effects)


def test_external_unmanaged_agent_adoption_remains_supported(deploy_behavior):
    behavior = deploy_behavior
    state = behavior.states["DB_A.AGENTS.SHARED"]
    state.update(
        comment="Externally created Agent",
        versions={"VERSION$1": ""},
        aliases={"DEFAULT": "VERSION$1", "LAST": "VERSION$1"},
        live=False,
    )
    behavior.deploy()
    behavior.deploy()
    assert len(state["versions"]) == 2
    assert state["aliases"]["DEFAULT"] == "VERSION$1"
    assert state["aliases"]["SANDBOX"] == "VERSION$2"
    assert sum(phase == "commit" for _, phase, _ in behavior.effects) == 1


@pytest.mark.parametrize("inspection", ["missing_comment", "empty", "missing_version_metadata"])
def test_unknown_creation_inspection_fails_before_mutation(deploy_behavior, inspection):
    behavior = deploy_behavior
    behavior.states["DB_A.AGENTS.SHARED"]["comment"] = "Managed by dbt cortex_agent materialization"

    def query(sql):
        if sql.startswith("DESCRIBE AGENT"):
            if inspection == "missing_comment":
                return Rows(["aliases"], [["{}"]])
            if inspection == "empty":
                return Rows(["comment"], [])
        if sql.startswith("SHOW VERSIONS") and inspection == "missing_version_metadata":
            return Rows(["name"], [["VERSION$1"]])
        return _deploy_query(behavior, sql)

    behavior.harness.context["run_query"] = query
    with pytest.raises(ValueError, match="explicit recovery required"):
        behavior.deploy()
    assert behavior.effects == []


def test_initial_version_metadata_acknowledgement_loss_retries_without_commit(deploy_behavior):
    behavior = deploy_behavior
    del behavior.states["DB_A.AGENTS.SHARED"]

    def query(sql):
        result = _deploy_query(behavior, sql)
        if " SET COMMENT " in sql:
            raise RuntimeError("metadata acknowledgement lost")
        return result

    behavior.harness.context["run_query"] = query
    with pytest.raises(RuntimeError, match="acknowledgement lost"):
        behavior.deploy()
    behavior.harness.context["run_query"] = lambda sql: _deploy_query(behavior, sql)
    behavior.deploy()
    assert len(behavior.states["DB_A.AGENTS.SHARED"]["versions"]) == 1
    assert all(phase != "commit" for _, phase, _ in behavior.effects)


@pytest.mark.parametrize("failure", ["alias_set", "live_add", "live_verify"])
def test_post_create_managed_metadata_allows_safe_retry(deploy_behavior, failure):
    behavior = deploy_behavior
    del behavior.states["DB_A.AGENTS.SHARED"]
    behavior.fault["phase"] = failure
    with pytest.raises(RuntimeError):
        behavior.deploy()
    behavior.fault["phase"] = None
    behavior.deploy()
    assert len(behavior.states["DB_A.AGENTS.SHARED"]["versions"]) == 1
    assert all(phase != "commit" for _, phase, _ in behavior.effects)


@pytest.mark.parametrize("live", [True, False])
@pytest.mark.parametrize("reconcile_alias", [True, False])
def test_managed_no_change_repairs_live_without_commit_or_default(
    deploy_behavior, live, reconcile_alias
):
    behavior = deploy_behavior
    state = behavior.states["DB_A.AGENTS.SHARED"]
    state["versions"]["VERSION$2"] = "spec_md5=cc"
    state["live"] = live
    before_versions = copy.deepcopy(state["versions"])
    behavior.deploy(reconcile_alias=reconcile_alias)
    assert state["live"] is True
    assert state["versions"] == before_versions
    assert state["aliases"]["DEFAULT"] == "VERSION$1"
    assert state["aliases"]["SANDBOX"] == ("VERSION$2" if reconcile_alias else "VERSION$1")
    assert sum(phase == "live_add" for _, phase, _ in behavior.effects) == (not live)
    assert all(phase not in {"commit", "spec"} for _, phase, _ in behavior.effects)
    phases = _dbt_phases("\n".join(behavior.logs), OperationOutcome()).to_dict()
    assert {
        "phase": "live_reconciled",
        "completed": True,
        "agent_fqn": "DB_A.AGENTS.SHARED",
    } in phases


@pytest.mark.parametrize(
    "failure",
    ["metadata", "alias_unset", "alias_set", "live_add", "live_verify", "live_postcondition"],
)
def test_durable_deploy_failure_retry_converges(deploy_behavior, failure):
    behavior = deploy_behavior
    behavior.fault["phase"] = failure
    with pytest.raises((RuntimeError, ValueError)):
        behavior.deploy()
    outcome = _dbt_phases("\n".join(behavior.logs), OperationOutcome())
    assert outcome.phases[0].phase is LifecyclePhase.VERSION_COMMITTED
    assert all(phase.agent_fqn == "DB_A.AGENTS.SHARED" for phase in outcome.phases)
    assert LifecyclePhase.LIVE_RECONCILED not in {phase.phase for phase in outcome.phases}
    assert behavior.states["DB_A.AGENTS.SHARED"]["aliases"]["DEFAULT"] == "VERSION$1"
    behavior.fault["phase"] = None
    behavior.deploy()
    behavior.deploy()
    state = behavior.states["DB_A.AGENTS.SHARED"]
    assert list(state["versions"]) == ["VERSION$1", "VERSION$2", "VERSION$3"]
    assert state["aliases"]["SANDBOX"] == "VERSION$3"
    assert state["aliases"]["DEFAULT"] == "VERSION$1"
    assert state["live"] is True
    assert sum(phase == "commit" for _, phase, _ in behavior.effects) == 1


@pytest.mark.parametrize("failure", ["live_add", "live_verify", "live_postcondition"])
def test_no_change_live_failure_retry_verifies_without_commit(deploy_behavior, failure):
    behavior = deploy_behavior
    state = behavior.states["DB_A.AGENTS.SHARED"]
    state["versions"]["VERSION$2"] = "spec_md5=cc"
    state["aliases"]["SANDBOX"] = "VERSION$2"
    state["live"] = False
    behavior.fault["phase"] = failure
    with pytest.raises((RuntimeError, ValueError)):
        behavior.deploy()
    phases = _dbt_phases("\n".join(behavior.logs), OperationOutcome())
    assert phases.phases == ()
    behavior.fault["phase"] = None
    behavior.deploy()
    assert state["live"] is True
    assert len(state["versions"]) == 2
    assert state["aliases"]["DEFAULT"] == "VERSION$1"
    assert all(phase == "live_add" for _, phase, _ in behavior.effects)


@pytest.mark.parametrize("error_type", [AssertionError, TypeError, AttributeError])
def test_deploy_programming_error_after_commit_propagates(deploy_behavior, tmp_path, error_type):
    behavior = deploy_behavior
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])

    def query(sql):
        if " SET COMMENT " in sql:
            raise error_type("programming defect after commit")
        return _deploy_query(behavior, sql)

    def run(command, **kwargs):
        behavior.deploy()
        pytest.fail("programming defect was swallowed")

    behavior.harness.context["run_query"] = query
    with pytest.raises(error_type, match="programming defect after commit"):
        apply_deploy_plan(plan, _config(tmp_path), runner=CommandRunner(run))
    assert sum(phase == "commit" for _, phase, _ in behavior.effects) == 1


def test_multi_agent_durable_outcomes_survive_failure_and_retry(deploy_behavior, tmp_path):
    behavior = deploy_behavior
    config = _config(tmp_path)
    plan = build_deploy_plan(_manifest(), config, ["agent_a", "agent_b"])
    behavior.fault.update(agent="DB_B.AGENTS.SHARED", phase="live_add")

    def run(command, **kwargs):
        behavior.logs.clear()
        try:
            for agent in plan.agents:
                behavior.deploy(agent["physical_fqn"])
        except RuntimeError as exc:
            return subprocess.CompletedProcess(
                command, 1, "\n".join(behavior.logs), "\n".join([*behavior.logs, str(exc)])
            )
        return subprocess.CompletedProcess(command, 0, "\n".join(behavior.logs), "")

    with pytest.raises(DurablePhaseError) as failure:
        apply_deploy_plan(plan, config, runner=CommandRunner(run))
    phases = failure.value.outcome.to_dict()
    for agent in plan.agents:
        assert {
            "agent_fqn": agent["physical_fqn"],
            "phase": "version_committed",
            "completed": True,
        } in phases
    assert [phase["agent_fqn"] for phase in phases if phase["phase"] == "live_reconciled"] == [
        "DB_A.AGENTS.SHARED"
    ]
    behavior.fault["phase"] = None
    retried = apply_deploy_plan(plan, config, runner=CommandRunner(run)).to_dict()
    assert [phase["agent_fqn"] for phase in retried if phase["phase"] == "live_reconciled"] == [
        "DB_A.AGENTS.SHARED",
        "DB_B.AGENTS.SHARED",
    ]
    assert sum(phase == "commit" for _, phase, _ in behavior.effects) == 2


def test_structured_markers_deduplicate_only_same_agent_and_phase():
    messages = [
        {"agent_fqn": agent, "phase": "version_committed"}
        for agent in ["DB_A.AGENTS.SHARED", "DB_B.AGENTS.SHARED", "db_a.agents.shared"]
    ]
    output = "\n".join("CORTEX_AGENT_DEPLOY_PHASE=" + json.dumps(item) for item in messages)
    output += '\nCORTEX_AGENT_DEPLOY_PHASE={"phase": "version_committed"}'
    output += "\nCORTEX_AGENT_DEPLOY_PHASE={broken"
    outcome = _dbt_phases(output, OperationOutcome())
    assert [phase.agent_fqn for phase in outcome.phases] == [
        "DB_A.AGENTS.SHARED",
        "DB_B.AGENTS.SHARED",
    ]


@pytest.mark.parametrize("invalid", ["target", "database", "identifier", "parse"])
def test_live_repair_helper_cannot_bypass_mutation_guards(deploy_behavior, invalid):
    behavior = deploy_behavior
    harness = behavior.harness
    agent_fqn = "DB_A.AGENTS.SHARED"
    harness.context["run_query"] = lambda sql: pytest.fail("guard allowed remote operation")
    if invalid == "target":
        harness.context["target"] = SimpleNamespace(name="production")
    elif invalid == "database":
        agent_fqn = "OTHER.AGENTS.SHARED"
    elif invalid == "identifier":
        agent_fqn = "DB_A.AGENTS.BAD;DROP"
    else:
        harness.context["execute"] = False
        assert harness.call("cortex_agent__reconcile_live", agent_fqn) is None
        return
    with pytest.raises(ValueError):
        harness.call("cortex_agent__reconcile_live", agent_fqn)


def _config(tmp_path):
    class Args:
        project_dir = str(tmp_path)
        manifest = None
        target = "sandbox"
        connection = "named"
        database = "DB_A"
        schema = None
        role = "ROLE"
        warehouse = "WH"
        artifact_dir = None
        dbt_executable = "dbt"
        snow_executable = "snow"

    return resolve_config(Args(), {})


def _manifest():
    return {
        "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
        "nodes": {
            "model.x.agent_a": {
                "unique_id": "model.x.agent_a",
                "resource_type": "model",
                "name": "agent_a",
                "database": "DB_A",
                "schema": "AGENTS",
                "alias": "SHARED",
                "config": {"materialized": "cortex_agent", "meta": {}},
            },
            "model.x.agent_b": {
                "unique_id": "model.x.agent_b",
                "resource_type": "model",
                "name": "agent_b",
                "database": "DB_B",
                "schema": "AGENTS",
                "alias": "SHARED",
                "config": {"materialized": "cortex_agent", "meta": {}},
            },
            "model.x.upstream": {
                "unique_id": "model.x.upstream",
                "resource_type": "model",
                "name": "upstream",
                "database": "DATA_DB",
                "schema": "MART",
                "alias": "UPSTREAM",
                "config": {"materialized": "table"},
            },
        },
        "parent_map": {
            "model.x.agent_a": ["model.x.upstream"],
            "model.x.agent_b": [],
            "model.x.upstream": [],
        },
    }


def test_deploy_plan_keeps_physical_identity_and_dependency_selection(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a", "agent_b"])

    assert [item["physical_fqn"] for item in plan.agents] == [
        "DB_A.AGENTS.SHARED",
        "DB_B.AGENTS.SHARED",
    ]
    assert plan.dbt_selection == ("+agent_a", "+agent_b")
    assert plan.resource_databases == ("DATA_DB", "DB_A", "DB_B")


@pytest.mark.parametrize("indirect", [False, True])
@pytest.mark.parametrize("disabled", [False, True])
@pytest.mark.parametrize("graph_source", ["parent_map", "depends_on", "both"])
def test_unselected_agent_ancestor_rejected_before_skill_planning(
    tmp_path, monkeypatch, indirect, disabled, graph_source
):
    manifest = _manifest()
    child = "model.x.upstream" if indirect else "model.x.agent_a"
    if graph_source != "depends_on":
        manifest["parent_map"][child] = ["model.x.agent_b"]
    if graph_source != "parent_map":
        manifest["nodes"][child]["depends_on"] = {"nodes": ["model.x.agent_b"]}
    manifest["nodes"]["model.x.agent_b"]["config"]["meta"] = {
        "cortex_agent": {"enabled": not disabled}
    }
    monkeypatch.setattr(
        "dbt_cortex_agent.deployment.build_upload_plan",
        lambda *args: pytest.fail("unapproved closure reached skill planning"),
    )
    with pytest.raises(ValueError, match="Unselected Agent ancestor.*model.x.agent_b"):
        build_deploy_plan(manifest, _config(tmp_path), ["agent_a"])


def test_explicit_agent_ancestor_includes_skills_and_resource_databases(tmp_path):
    manifest = _manifest()
    manifest["parent_map"]["model.x.upstream"] = ["model.x.agent_b"]
    manifest["nodes"]["model.x.agent_b"]["config"]["meta"] = {
        "cortex_agent": {
            "skills": [
                {
                    "name": "ancestor_skill",
                    "source": {"type": "stage", "path": "@SKILL_DB.PUBLIC.SKILLS/library/ancestor"},
                }
            ]
        }
    }
    skill_dir = tmp_path / "skills/library/ancestor"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("Synthetic ancestor skill", encoding="utf-8")
    plan = build_deploy_plan(manifest, _config(tmp_path), ["agent_a", "agent_b"])
    assert [agent["unique_id"] for agent in plan.agents] == ["model.x.agent_a", "model.x.agent_b"]
    assert plan.skill_uploads[0].agent_names == ("agent_b",)
    assert plan.resource_databases == ("DATA_DB", "DB_A", "DB_B", "SKILL_DB")
    with pytest.raises(ValueError, match="SKILL_DB"):
        validate_deploy_plan(plan, _config(tmp_path), ["sandbox"], ["DATA_DB", "DB_A", "DB_B"])


@pytest.mark.parametrize("drift", ["database", "schema", "identifier", "unexpected", "none"])
def test_apply_expected_identity_reaches_materialization_before_effects(
    tmp_path, macro_harness, drift
):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])
    relation = SimpleNamespace(database="DB_A", schema="AGENTS", identifier="SHARED")
    model = SimpleNamespace(name="agent_a", unique_id="model.x.agent_a")
    effects = []
    if drift in {"database", "schema", "identifier"}:
        setattr(relation, drift, "OTHER")
    elif drift == "unexpected":
        model.unique_id = "model.x.agent_b"
    macro_harness.context.update(
        this=relation,
        model=model,
        config={"meta": {}},
        target=SimpleNamespace(name="sandbox"),
        sql="models:\n  orchestration: test-model\n",
        pre_hooks=["pre"],
        post_hooks=["post"],
        run_hooks=lambda *args, **kwargs: effects.append("hook") or "",
        statement=lambda name, caller: effects.append(caller()) or "",
    )
    macro_harness.override(
        "cortex_agent__assert_staged_skills_ready", lambda spec: effects.append("skills")
    )
    macro_harness.override("cortex_agent__skills_hash", lambda spec: "")
    macro_harness.override("cortex_agent__apply_deploy", lambda *args: effects.append(args[0]))

    def run(command, **kwargs):
        variables = json.loads(command[command.index("--vars") + 1])
        assert variables["cortex_agent_expected_fqns"] == {"model.x.agent_a": "DB_A.AGENTS.SHARED"}
        variables.update(
            cortex_agent_allowed_targets=["sandbox"],
            cortex_agent_allowed_databases=["DB_A", "OTHER"],
        )
        macro_harness.context["var"] = lambda name, default=None: variables.get(name, default)
        try:
            macro_harness.call("materialization_cortex_agent")
        except ValueError as exc:
            return subprocess.CompletedProcess(command, 1, "", str(exc))
        return subprocess.CompletedProcess(command, 0, "", "")

    if drift == "none":
        apply_deploy_plan(plan, _config(tmp_path), runner=CommandRunner(run))
        assert "DB_A.AGENTS.SHARED" in effects
        assert effects[0] == "hook"
    else:
        with pytest.raises(DurablePhaseError, match="identity changed|Unexpected Agent"):
            apply_deploy_plan(plan, _config(tmp_path), runner=CommandRunner(run))
        assert effects == []


def test_deploy_plan_requires_complete_resource_allowlist(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a", "agent_b"])

    with pytest.raises(ValueError, match="DB_B"):
        validate_deploy_plan(plan, _config(tmp_path), ["sandbox"], ["DB_A", "DATA_DB"])


def test_connection_database_does_not_narrow_multi_database_resource_scope(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a", "agent_b"])

    validate_deploy_plan(
        plan,
        _config(tmp_path),
        ["sandbox"],
        ["DB_A", "DB_B", "DATA_DB"],
    )


def test_deploy_plan_requires_dependency_database_allowlist(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])

    with pytest.raises(ValueError, match="DATA_DB"):
        validate_deploy_plan(plan, _config(tmp_path), ["sandbox"], ["DB_A"])


def test_apply_runs_dbt_build_after_skill_phase(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    outcome = apply_deploy_plan(plan, _config(tmp_path), runner=CommandRunner(run))

    assert calls == [
        [
            "dbt",
            "build",
            "--project-dir",
            str(tmp_path),
            "--target",
            "sandbox",
            "--select",
            "+agent_a",
            "--vars",
            '{"cortex_agent_expected_fqns":{"model.x.agent_a":"DB_A.AGENTS.SHARED"}}',
        ]
    ]
    assert [item["phase"] for item in outcome.to_dict()] == [
        "preflight",
        "skills_uploaded",
        "verified",
    ]


def test_apply_passes_exact_multi_agent_map_without_changing_child_context(tmp_path):
    config = _config(tmp_path)
    plan = build_deploy_plan(_manifest(), config, ["agent_a", "agent_b"])

    def run(command, **kwargs):
        assert json.loads(command[command.index("--vars") + 1]) == {
            "cortex_agent_expected_fqns": {
                "model.x.agent_a": "DB_A.AGENTS.SHARED",
                "model.x.agent_b": "DB_B.AGENTS.SHARED",
            }
        }
        assert kwargs["cwd"] == config.project_dir
        assert kwargs.get("env") == config.dbt_env
        return subprocess.CompletedProcess(command, 0, "ok", "")

    apply_deploy_plan(plan, config, runner=CommandRunner(run))


def test_dbt_failure_reports_reconciliation_as_indeterminate(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])

    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "dbt failed", "")

    with pytest.raises(DurablePhaseError) as exc:
        apply_deploy_plan(plan, _config(tmp_path), runner=CommandRunner(run))

    failed = exc.value.outcome.phases[-1]
    assert failed.phase is LifecyclePhase.VERIFIED
    assert failed.completed is False
    assert "indeterminate" in str(failed.detail)


def test_dbt_phase_markers_are_deduplicated_and_unknown_markers_ignored():
    output = """CORTEX_AGENT_DEPLOY_PHASE=version_committed
CORTEX_AGENT_DEPLOY_PHASE=version_committed
CORTEX_AGENT_DEPLOY_PHASE=future_phase
CORTEX_AGENT_DEPLOY_PHASE=metadata_reconciled
"""

    outcome = _dbt_phases(output, OperationOutcome())

    assert [item.phase for item in outcome.phases] == [
        LifecyclePhase.VERSION_COMMITTED,
        LifecyclePhase.METADATA_RECONCILED,
    ]


def test_dbt_failure_preserves_markers_from_stdout_and_stderr(tmp_path):
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])

    def run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            1,
            "CORTEX_AGENT_DEPLOY_PHASE=version_committed",  # pragma: allowlist secret
            "CORTEX_AGENT_DEPLOY_PHASE=metadata_reconciled\ndbt failed",
        )

    with pytest.raises(DurablePhaseError) as exc:
        apply_deploy_plan(plan, _config(tmp_path), runner=CommandRunner(run))

    assert [item.phase for item in exc.value.outcome.phases] == [
        LifecyclePhase.PREFLIGHT,
        LifecyclePhase.SKILLS_UPLOADED,
        LifecyclePhase.VERSION_COMMITTED,
        LifecyclePhase.METADATA_RECONCILED,
        LifecyclePhase.VERIFIED,
    ]


def test_skill_upload_programming_error_is_not_reported_as_durable_failure(
    monkeypatch, tmp_path
) -> None:
    plan = build_deploy_plan(_manifest(), _config(tmp_path), ["agent_a"])
    monkeypatch.setattr(
        "dbt_cortex_agent.deployment.upload_skills",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("programming defect")),
    )

    with pytest.raises(AssertionError, match="programming defect"):
        apply_deploy_plan(plan, _config(tmp_path))
