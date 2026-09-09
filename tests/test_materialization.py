import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]

# Evidence: TC-023-02 TC-023-04 TC-023-05 TC-023-07 TC-023-09 TC-023-12 TC-025-10


def test_python_owns_no_mutating_agent_ddl_or_lifecycle_module():
    source_root = ROOT / "src/dbt_cortex_agent"
    mutating_agent_ddl = re.compile(
        r"\b(?:CREATE(?:\s+OR\s+REPLACE)?|ALTER|DROP)\s+AGENT\b", re.IGNORECASE
    )

    offenders = [
        str(path.relative_to(source_root))
        for path in source_root.rglob("*.py")
        if mutating_agent_ddl.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []
    assert not (source_root / "deploy.py").exists()


def test_materialization_is_the_agent_lifecycle_authority():
    materialization = (ROOT / "macros/materializations/cortex_agent.sql").read_text(
        encoding="utf-8"
    )
    lifecycle = (ROOT / "macros/cortex_agents/agent_render.sql").read_text(encoding="utf-8")

    assert "{% materialization cortex_agent, adapter='snowflake' %}" in materialization
    assert "cortex_agent__materialization_spec(sql, model.name)" in materialization
    assert "cortex_agent__assert_staged_skills_ready(spec)" in materialization
    assert "cortex_agent__skills_hash(spec)" in materialization
    assert "dbt_cortex_agent.cortex_agent__apply_deploy" in materialization
    assert "return({'relations': []})" in materialization
    assert "macro cortex_agent__apply_deploy" in lifecycle
    assert "CREATE AGENT " in lifecycle and "FROM SPECIFICATION" in lifecycle
    assert "MODIFY LIVE VERSION SET SPECIFICATION" in lifecycle
    assert 'run_query("ALTER AGENT " ~ agent_fqn ~ " COMMIT COMMENT = $$"' in lifecycle
    assert "cortex_agent__route_alias_for_fqn" in lifecycle
    assert "CORTEX_AGENT_DEPLOY_PHASE=version_committed" in lifecycle  # pragma: allowlist secret
    assert "CORTEX_AGENT_DEPLOY_PHASE=metadata_reconciled" in lifecycle  # pragma: allowlist secret
    assert "CORTEX_AGENT_DEPLOY_PHASE=alias_reconciled" in lifecycle  # pragma: allowlist secret
    assert "CORTEX_AGENT_DEPLOY_PHASE=live_reconciled" in lifecycle  # pragma: allowlist secret

    versioning = (ROOT / "macros/cortex_agents/agent_versioning.sql").read_text(encoding="utf-8")
    alias_phase = versioning[
        versioning.index("macro cortex_agent__route_alias") : versioning.index(
            "macro cortex_agent__route_default"
        )
    ]
    default_phase = versioning[
        versioning.index("macro cortex_agent__route_default") : versioning.index(
            "macro cortex_agent__route_version"
        )
    ]
    assert "SET ALIAS" in alias_phase and "DEFAULT_VERSION" not in alias_phase
    assert "SET DEFAULT_VERSION" in default_phase and "SET ALIAS" not in default_phase
    assert "cortex_agent__routing_alias" in lifecycle
    assert "cortex_agent__route_alias_for_fqn" in lifecycle
    assert "cortex_agent__route_alias_for_fqn" in versioning
    assert "Agent alias changed after planning" in versioning


def test_materialization_requires_explicit_orchestration():
    materialization = (ROOT / "macros/materializations/cortex_agent.sql").read_text(
        encoding="utf-8"
    )

    assert "must explicitly define models.orchestration" in materialization
    assert "cortex_agent_default_model" not in materialization


def test_materialization_uses_invoking_role_and_nontransactional_hooks():
    materialization = (ROOT / "macros/materializations/cortex_agent.sql").read_text(
        encoding="utf-8"
    )

    deploy = materialization.index("cortex_agent__apply_deploy")
    pre_hook = materialization.index("run_hooks(pre_hooks, inside_transaction=False)")
    post_hook = materialization.index("run_hooks(post_hooks, inside_transaction=False)")
    assert pre_hook < deploy < post_hook
    assert "USE ROLE" not in materialization
    assert "adapter.commit" not in materialization
    assert "inside_transaction=True" not in materialization


def test_staged_skill_paths_are_validated_before_list():
    lifecycle = (ROOT / "macros/cortex_agents/agent_render.sql").read_text(encoding="utf-8")

    assert "macro cortex_agent__stage_path" in lifecycle
    assert lifecycle.count("dbt_cortex_agent.cortex_agent__stage_path(") == 2
    assert "part in ['.', '..']" in lifecycle


def test_no_change_build_skips_commit_and_can_reconcile_alias():
    lifecycle = (ROOT / "macros/cortex_agents/agent_render.sql").read_text(encoding="utf-8")
    no_change = lifecycle[
        lifecycle.index("managed_version =") : lifecycle.index("{% if not existed %}")
    ]

    assert "reconcile_alias and expected_alias_version != managed_version" in no_change
    assert "cortex_agent__route_alias_for_fqn" in no_change
    assert 'run_query("ALTER AGENT " ~ agent_fqn ~ " COMMIT")' not in no_change


def test_idempotency_is_independent_of_serving_default():
    lifecycle = (ROOT / "macros/cortex_agents/agent_render.sql").read_text(encoding="utf-8")
    managed = lifecycle[
        lifecycle.index("macro cortex_agent__managed_version") : lifecycle.index(
            "macro cortex_agent__skills_hash"
        )
    ]

    assert "SHOW VERSIONS IN AGENT" in managed
    assert "spec_md5=" in managed and "skill_md5=" in managed
    executable_lines = "\n".join(
        line for line in managed.splitlines() if not line.lstrip().startswith("DEFAULT")
    )
    assert "aliases.get('DEFAULT')" not in executable_lines
    assert "current_deploy_hashes" not in lifecycle
    assert "current_spec_hash" not in lifecycle


def test_first_deploy_creates_agent_from_specification_without_extra_commit():
    lifecycle = (ROOT / "macros/cortex_agents/agent_render.sql").read_text(encoding="utf-8")
    apply = lifecycle[lifecycle.index("macro cortex_agent__apply_deploy") :]
    first_deploy = apply[apply.index("{% if not existed %}") : apply.index("{% else %}")]

    assert "CREATE AGENT " in first_deploy
    assert "FROM SPECIFICATION" in first_deploy
    assert " COMMIT" not in first_deploy


def test_enterprise_materialization_body_remains_full_agent_yaml():
    fixture = (
        ROOT / "integration_tests/models/agents/enterprise_compatibility_probe.sql"
    ).read_text(encoding="utf-8")
    helper = (ROOT / "integration_tests/macros/enterprise_compatibility.sql").read_text(
        encoding="utf-8"
    )
    helper_body = helper.split("%}", 1)[1].rsplit("{% endmacro", 1)[0].strip()
    body = "models:\n" + fixture.split("\nmodels:\n", 1)[1]
    invocation = "{{ enterprise_compatibility_orchestration_instructions() | indent(4) }}"
    rendered = body.replace(
        invocation,
        "\n" + "\n".join("    " + line for line in helper_body.splitlines()),
    )
    spec = yaml.safe_load(rendered)

    assert spec["models"]["orchestration"] == "claude-opus-4-8"
    assert spec["mcp_servers"] and spec["skills"]


def test_python_cli_exposes_smoke_but_no_agent_lifecycle_commands():
    command = (ROOT / "src/dbt_cortex_agent/commands/agent.py").read_text(encoding="utf-8")

    assert 'commands.add_parser(\n        "smoke"' in command
    for removed in ("render", "grant"):
        assert f'commands.add_parser("{removed}"' not in command
