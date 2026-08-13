from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_execution_plan_macro_is_offline_and_reuses_authoritative_helpers():
    source = (ROOT / "macros/cortex_agents/eval_render.sql").read_text(encoding="utf-8")
    body = source.split("{% macro cortex_eval__execution_plan", 1)[1].split("{% endmacro %}", 1)[0]
    assert "run_query(" not in body
    for helper in (
        "cortex_eval__get_suite",
        "cortex_eval__validate",
        "cortex_agent__resource_agent_fqn",
        "cortex_eval__dataset_fqn",
        "cortex_eval__native_config",
        "cortex_eval__default_stage_fqn",
    ):
        assert helper in body
    assert "CORTEX_EVAL_PLAN_JSON=" in body
    assert "suite_signature" in body
    assert "projection" not in body


def test_eval_macros_never_invoke_agent_lifecycle_or_emit_projection_identity():
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "macros/cortex_agents").glob("eval*.sql"))
    )
    for forbidden in (
        "cortex_agent__deploy(",
        "cortex_agent__build(",
        "CREATE AGENT",
        "ALTER AGENT",
        "'projection',",
        '"projection":',
    ):
        assert forbidden not in sources


def test_python_eval_lifecycle_does_not_reconstruct_dbt_owned_plan_fields():
    source = (ROOT / "src/dbt_cortex_agent/eval/lifecycle.py").read_text(encoding="utf-8")
    for obsolete in (
        "def _resolve_agent_object",
        "cortex_evals(",
        "select_agents(",
        "validate_eval_meta(",
        '"dataset": {',
        '"evaluation": {',
    ):
        assert obsolete not in source


def test_eval_metadata_contract_rejects_projection_and_validates_full_spec_tools():
    source = (ROOT / "macros/cortex_agents/eval_contract.sql").read_text(encoding="utf-8")
    assert "must not define config.meta.cortex_eval.projection" in source
    assert "cortex_eval__native_supported_tool_names(eval_meta.get('agent'))" in source
    assert "cannot claim native coverage" in source
    assert "undeclared or unsupported native tool" in source


def test_capability_evidence_uses_only_req_013_classifications():
    source = (ROOT / "macros/cortex_agents/eval_contract.sql").read_text(encoding="utf-8")
    body = source.split("{% macro cortex_eval__capability_evidence", 1)[1].split(
        "{% endmacro %}", 1
    )[0]
    classifications = {
        "attached",
        "invoked",
        "completed_with_attachment",
        "absent",
        "indeterminate",
    }
    for classification in classifications:
        assert f"'{classification}'" in body
    assert "evaluation_completed" in body
    assert "invoked_tools" in body
    assert "CORTEX_AGENT_CAPABILITY_EVIDENCE=" in source


def test_native_expected_tool_classes_are_explicit_and_do_not_filter_deploy_spec():
    source = (ROOT / "macros/cortex_agents/eval_contract.sql").read_text(encoding="utf-8")
    supported = source.split("{% macro cortex_eval__native_supported_tool_names", 1)[1].split(
        "{% endmacro %}", 1
    )[0]
    for tool_type in (
        "cortex_analyst_text_to_sql",
        "cortex_search",
        "generic",
        "web_search",
    ):
        assert tool_type in supported
    unsupported = source.split("{% macro cortex_eval__unsupported_native_tool_claims", 1)[1].split(
        "{% endmacro %}", 1
    )[0]
    for capability in ("skills", "mcp_connectors", "code_execution"):
        assert capability in unsupported

    render_source = (ROOT / "macros/cortex_agents/agent_render.sql").read_text(encoding="utf-8")
    assert "evaluation_supported" not in render_source
    assert "expected_tools must be a list of tool names" in source
    assert "expected_tools entries must be non-empty strings" in source


def test_obsolete_evaluation_supported_declarations_are_removed():
    paths = [
        ROOT / "src/dbt_cortex_agent/starters/orders/models/agents/orders_assistant/agent.yml",
        ROOT / "integration_tests/models/agents/orders_assistant/agent.yml",
        ROOT / "integration_tests/docs/progressive-features.md",
        ROOT / "docs/guides/mcp.md",
    ]
    for path in paths:
        assert "evaluation_supported:" not in path.read_text(encoding="utf-8")


def test_declared_tool_wins_if_a_capability_reuses_its_name():
    source = (ROOT / "macros/cortex_agents/eval_contract.sql").read_text(encoding="utf-8")
    validation = source.split("{% macro cortex_eval__validate", 1)[1].split(
        "{% endmacro %}", 1
    )[0]
    supported_branch = validation.index("expected_tool in native_supported_tool_names")
    unsupported_branch = validation.index("unsupported_native_tool_claims.get(expected_tool)")
    assert supported_branch < unsupported_branch