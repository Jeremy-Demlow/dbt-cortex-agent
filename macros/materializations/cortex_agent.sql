{% macro cortex_agent__sql_literal(value, label) %}
  {% if value is not string %}
    {{ exceptions.raise_compiler_error(label ~ ' must be a string') }}
  {% endif %}
  {{ return("'" ~ (value | replace("'", "''")) ~ "'") }}
{% endmacro %}

{% macro cortex_agent__materialization_spec(specification, model_name) %}
  {% set spec = fromyaml(specification) %}
  {% if spec is not mapping %}
    {{ exceptions.raise_compiler_error("cortex_agent model '" ~ model_name ~ "' must compile to a YAML mapping") }}
  {% endif %}
  {% set models = spec.get('models') %}
  {% if models is not mapping or not (models.get('orchestration') | default('', true) | trim) %}
    {{ exceptions.raise_compiler_error("cortex_agent model '" ~ model_name ~ "' must explicitly define models.orchestration") }}
  {% endif %}
  {{ return(spec) }}
{% endmacro %}

{% materialization cortex_agent, adapter='snowflake' %}
  {% set target_relation = this %}
  {% set metadata = config.get('meta', {}) %}
  {% set agent_comment = metadata.get('agent_comment', 'Managed by dbt-cortex-agent') %}
  {% set agent_display_name = metadata.get('agent_display_name', this.identifier) %}
  {% set deploy_alias = metadata.get('deploy_alias', target.name) %}
  {% set safe_alias = dbt_cortex_agent.cortex_agent__routing_alias(deploy_alias, 'deploy alias') %}
  {% set safe_agent_fqn = dbt_cortex_agent.cortex_agent__unquoted_fqn(
      target_relation.database ~ '.' ~ target_relation.schema ~ '.' ~ target_relation.identifier,
      'cortex_agent model relation'
  ) %}
  {% set missing_expectations = namespace() %}
  {% set expected_fqns = var('cortex_agent_expected_fqns', missing_expectations) %}
  {% if expected_fqns is not sameas missing_expectations %}
    {% if expected_fqns is not mapping %}
      {{ exceptions.raise_compiler_error('cortex_agent_expected_fqns must be a mapping of unique_id to physical FQN') }}
    {% endif %}
    {% if model.unique_id not in expected_fqns or expected_fqns[model.unique_id] is not string %}
      {{ exceptions.raise_compiler_error('Unexpected Agent materialization or missing planned FQN: ' ~ model.unique_id) }}
    {% endif %}
    {% do dbt_cortex_agent.cortex_agent__assert_expected_identity(safe_agent_fqn, expected_fqns[model.unique_id]) %}
  {% endif %}
  {% set spec = dbt_cortex_agent.cortex_agent__materialization_spec(sql, model.name) %}
  {% set spec_json = tojson(spec) %}
  {% set profile_json = tojson({'display_name': agent_display_name}) %}

  {% if '$$' in spec_json or '$$' in profile_json %}
    {{ exceptions.raise_compiler_error("cortex_agent model '" ~ model.name ~ "' contains the reserved $$ delimiter") }}
  {% endif %}

  {% do dbt_cortex_agent.cortex_agent__assert_deploy_target('cortex_agent materialization') %}
  {% do dbt_cortex_agent.cortex_agent__assert_database_allowed('cortex_agent materialization', target_relation.database) %}

  {{ run_hooks(pre_hooks, inside_transaction=False) }}

  {% do dbt_cortex_agent.cortex_agent__assert_staged_skills_ready(spec) %}
  {% set skill_hash = dbt_cortex_agent.cortex_agent__skills_hash(spec) %}
  {% do dbt_cortex_agent.cortex_agent__apply_deploy(safe_agent_fqn, spec_json, safe_alias, [], skill_hash, true) %}

  {% call statement('main') %}
    ALTER AGENT {{ safe_agent_fqn }} SET COMMENT = {{ dbt_cortex_agent.cortex_agent__sql_literal(agent_comment, 'agent_comment') }}
  {% endcall %}
  {% call statement('set_cortex_agent_profile') %}
    ALTER AGENT {{ safe_agent_fqn }} SET PROFILE = $$ {{ profile_json }} $$
  {% endcall %}

  {{ run_hooks(post_hooks, inside_transaction=False) }}

  {{ return({'relations': []}) }}
{% endmaterialization %}