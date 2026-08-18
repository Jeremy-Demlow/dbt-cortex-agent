from pathlib import Path
import re

import yaml


ROOT = Path(__file__).parents[1]


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
    materialization = (
        ROOT / "macros/materializations/cortex_agent.sql"
    ).read_text(encoding="utf-8")
    lifecycle = (
        ROOT / "macros/cortex_agents/agent_render.sql"
    ).read_text(encoding="utf-8")

    assert "{% materialization cortex_agent, adapter='snowflake' %}" in materialization
    assert "cortex_agent__materialization_spec(sql, model.name)" in materialization
    assert "cortex_agent__assert_staged_skills_ready(spec)" in materialization
    assert "cortex_agent__skills_hash(spec)" in materialization
    assert "dbt_cortex_agent.cortex_agent__apply_deploy" in materialization
    assert "return({'relations': []})" in materialization
    assert "macro cortex_agent__apply_deploy" in lifecycle
    assert "CREATE AGENT IF NOT EXISTS" in lifecycle
    assert "MODIFY LIVE VERSION SET SPECIFICATION" in lifecycle
    assert 'run_query("ALTER AGENT " ~ agent_fqn ~ " COMMIT")' in lifecycle
    assert "SET ALIAS = " in lifecycle


def test_materialization_requires_explicit_orchestration():
    materialization = (
        ROOT / "macros/materializations/cortex_agent.sql"
    ).read_text(encoding="utf-8")

    assert "must explicitly define models.orchestration" in materialization
    assert "cortex_agent_default_model" not in materialization


def test_materialization_role_and_hook_order_is_explicit():
    materialization = (
        ROOT / "macros/materializations/cortex_agent.sql"
    ).read_text(encoding="utf-8")

    set_role = materialization.index("USE ROLE {{ safe_agent_role }}")
    deploy = materialization.index("cortex_agent__apply_deploy")
    post_hook = materialization.index("run_hooks(post_hooks, inside_transaction=True)")
    restore_role = materialization.index("USE ROLE {{ safe_original_role }}")
    assert set_role < deploy < post_hook < restore_role


def test_staged_skill_paths_are_validated_before_list():
    lifecycle = (
        ROOT / "macros/cortex_agents/agent_render.sql"
    ).read_text(encoding="utf-8")

    assert "macro cortex_agent__stage_path" in lifecycle
    assert lifecycle.count("dbt_cortex_agent.cortex_agent__stage_path(") == 2
    assert "part in ['.', '..']" in lifecycle


def test_no_change_build_skips_commit_and_can_reconcile_alias():
    lifecycle = (
        ROOT / "macros/cortex_agents/agent_render.sql"
    ).read_text(encoding="utf-8")
    no_change = lifecycle[
        lifecycle.index("current_hashes.get('spec_md5')") : lifecycle.index(
            "{% if not existed %}"
        )
    ]

    assert "reconcile_alias and default_version" in no_change
    assert "MODIFY VERSION " in no_change and " SET ALIAS = " in no_change
    assert 'run_query("ALTER AGENT " ~ agent_fqn ~ " COMMIT")' not in no_change


def test_enterprise_materialization_body_remains_full_agent_yaml():
    fixture = (
        ROOT / "integration_tests/models/agents/enterprise_compatibility_probe.sql"
    ).read_text(encoding="utf-8")
    helper = (
        ROOT / "integration_tests/macros/enterprise_compatibility.sql"
    ).read_text(encoding="utf-8")
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
    command = (ROOT / "src/dbt_cortex_agent/commands/agent.py").read_text(
        encoding="utf-8"
    )

    assert 'commands.add_parser(\n        "smoke"' in command
    for removed in ("render", "deploy", "grant", "promote", "rollback"):
        assert f'commands.add_parser("{removed}"' not in command