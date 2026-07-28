{% macro cortex_agent__deploy_target() %}
  {# The single target name allowed to run mutating deploy/eval paths. Defaults
     to this project's sandbox; override for another environment via
     `--vars '{cortex_agent_deploy_target: my_sandbox}'`. #}
  {{ return(var('cortex_agent_deploy_target', 'dbt_focus')) }}
{% endmacro %}

{% macro cortex_agent__assert_deploy_target(context) %}
  {# Raise unless the active target is the allowed deploy target. Centralizes the
     sandbox guard so mutating paths cannot run against dev/prod by accident. #}
  {% set allowed = cortex_agent__deploy_target() %}
  {% if target.name != allowed %}
    {{ exceptions.raise_compiler_error(context ~ " mutating path is restricted to target=" ~ allowed ~ " (got '" ~ target.name ~ "'). Use dry_run=true elsewhere.") }}
  {% endif %}
{% endmacro %}

{% macro cortex_agent__schema() %}
  {{ return(var('cortex_agent_schema', 'AGENTS')) }}
{% endmacro %}

{% macro cortex_eval__schema() %}
  {{ return(var('cortex_eval_schema', 'EVAL')) }}
{% endmacro %}
