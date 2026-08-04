from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_execution_plan_macro_is_offline_and_reuses_authoritative_helpers():
    source = (ROOT / "macros/cortex_agents/eval_render.sql").read_text(encoding="utf-8")
    body = source.split("{% macro cortex_eval__execution_plan", 1)[1].split("{% endmacro %}", 1)[0]
    assert "run_query(" not in body
    for helper in (
        "cortex_eval__get_suite",
        "cortex_eval__validate",
        "cortex_agent__target_agent_fqn",
        "cortex_eval__dataset_fqn",
        "cortex_eval__native_config",
        "cortex_eval__default_stage_fqn",
    ):
        assert helper in body
    assert "CORTEX_EVAL_PLAN_JSON=" in body
    assert "suite_signature" in body


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