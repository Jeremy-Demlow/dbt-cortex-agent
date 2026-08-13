{% macro cortex_agent__deploy_target() %}
  {# Compatibility accessor for consumers still declaring one deploy target. #}
  {{ return(var('cortex_agent_deploy_target', 'dbt_focus')) }}
{% endmacro %}

{% macro cortex_agent__allowed_targets() %}
  {{ return(var('cortex_agent_allowed_targets', [dbt_cortex_agent.cortex_agent__deploy_target()])) }}
{% endmacro %}

{% macro cortex_agent__allowed_databases() %}
  {{ return(var('cortex_agent_allowed_databases', [])) }}
{% endmacro %}

{% macro cortex_agent__assert_deploy_target(context) %}
  {% set allowed_targets = dbt_cortex_agent.cortex_agent__allowed_targets() %}
  {% set allowed_databases = dbt_cortex_agent.cortex_agent__allowed_databases() | map('upper') | list %}
  {% if target.name not in allowed_targets %}
    {{ exceptions.raise_compiler_error(context ~ " mutating path target '" ~ target.name ~ "' is not in cortex_agent_allowed_targets=" ~ tojson(allowed_targets) ~ ". Use dry_run=true elsewhere.") }}
  {% endif %}
  {% if allowed_databases | length == 0 %}
    {{ exceptions.raise_compiler_error(context ~ " mutating path requires a non-empty cortex_agent_allowed_databases allowlist") }}
  {% endif %}
  {% if (target.database | upper) not in allowed_databases %}
    {{ exceptions.raise_compiler_error(context ~ " mutating path database '" ~ target.database ~ "' is not in cortex_agent_allowed_databases=" ~ tojson(allowed_databases)) }}
  {% endif %}
{% endmacro %}

{% macro cortex_agent__validate_deploy_context() %}
  {% do cortex_agent__assert_deploy_target('cortex_agent__validate_deploy_context') %}
  {% do log("Validated lifecycle allowlists for target=" ~ target.name ~ ", database=" ~ target.database, info=True) %}
  {{ return(true) }}
{% endmacro %}

{% macro cortex_agent__schema() %}
  {{ return(var('cortex_agent_schema', 'AGENTS')) }}
{% endmacro %}

{% macro cortex_eval__schema() %}
  {{ return(var('cortex_eval_schema', 'EVAL')) }}
{% endmacro %}
