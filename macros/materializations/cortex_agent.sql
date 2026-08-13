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
  {% set target_relation = api.Relation.create(
      database=config.get('database', this.database),
      schema=config.get('schema', this.schema),
      identifier=this.identifier
  ) %}
  {% set metadata = config.get('meta', {}) %}
  {% set agent_role = metadata.get('agent_role') %}
  {% set agent_comment = metadata.get('agent_comment', 'Managed by dbt-cortex-agent') %}
  {% set agent_display_name = metadata.get('agent_display_name', this.identifier) %}
  {% set deploy_alias = metadata.get('deploy_alias', target.name) %}
  {% set safe_alias = cortex_agent__unquoted_identifier(deploy_alias, 'deploy alias') %}
  {% set safe_agent_fqn = cortex_agent__unquoted_fqn(
      target_relation.database ~ '.' ~ target_relation.schema ~ '.' ~ target_relation.identifier,
      'cortex_agent model relation'
  ) %}
  {% set spec = cortex_agent__materialization_spec(sql, model.name) %}
  {% set spec_json = tojson(spec) %}
  {% set profile_json = tojson({'display_name': agent_display_name}) %}

  {% if '$$' in spec_json or '$$' in profile_json %}
    {{ exceptions.raise_compiler_error("cortex_agent model '" ~ model.name ~ "' contains the reserved $$ delimiter") }}
  {% endif %}

  {% do cortex_agent__assert_deploy_target('cortex_agent materialization') %}
  {% if (target_relation.database | upper) not in (cortex_agent__allowed_databases() | map('upper') | list) %}
    {{ exceptions.raise_compiler_error("cortex_agent materialization database '" ~ target_relation.database ~ "' is not in cortex_agent_allowed_databases=" ~ tojson(cortex_agent__allowed_databases())) }}
  {% endif %}

  {{ run_hooks(pre_hooks, inside_transaction=False) }}

  {% if agent_role %}
    {% set safe_agent_role = cortex_agent__unquoted_identifier(agent_role, 'agent role') %}
    {% call statement('capture_cortex_agent_role', fetch_result=True) %}
      SELECT CURRENT_ROLE()
    {% endcall %}
    {% set original_role = load_result('capture_cortex_agent_role')['data'][0][0] %}
    {% call statement('set_cortex_agent_role') %}
      USE ROLE {{ safe_agent_role }}
    {% endcall %}
  {% endif %}

  {{ run_hooks(pre_hooks, inside_transaction=True) }}

  {% do cortex_agent__assert_staged_skills_ready(spec) %}
  {% set skill_hash = cortex_agent__skills_hash(spec) %}
  {% do cortex_agent__apply_deploy(safe_agent_fqn, spec_json, safe_alias, [], skill_hash, true) %}

  {% call statement('main') %}
    ALTER AGENT {{ safe_agent_fqn }} SET COMMENT = {{ cortex_agent__sql_literal(agent_comment, 'agent_comment') }}
  {% endcall %}
  {% call statement('set_cortex_agent_profile') %}
    ALTER AGENT {{ safe_agent_fqn }} SET PROFILE = $$ {{ profile_json }} $$
  {% endcall %}

  {{ run_hooks(post_hooks, inside_transaction=True) }}
  {% do adapter.commit() %}
  {{ run_hooks(post_hooks, inside_transaction=False) }}

  {% if agent_role %}
    {% set safe_original_role = cortex_agent__unquoted_identifier(original_role, 'original role') %}
    {% call statement('restore_cortex_agent_role') %}
      USE ROLE {{ safe_original_role }}
    {% endcall %}
  {% endif %}

  {{ return({'relations': []}) }}
{% endmaterialization %}