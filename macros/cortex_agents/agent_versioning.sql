{% macro cortex_agent__describe_aliases(agent_fqn) %}
  {# Returns the aliases dict from DESCRIBE AGENT, e.g.
     {"DEFAULT":"VERSION$3","FIRST":"VERSION$1","LAST":"VERSION$3","LATEST":"VERSION$3"}.
     Reads DESCRIBE rather than the unreliable SHOW VERSIONS alias column. #}
  {% if not execute %}
    {{ return({}) }}
  {% endif %}
  {% set results = run_query("DESCRIBE AGENT " ~ agent_fqn) %}
  {% set col_names = results.column_names | map('lower') | list %}
  {% if 'aliases' not in col_names %}
    {{ return({}) }}
  {% endif %}
  {% set idx = col_names.index('aliases') %}
  {% set raw = results.rows[0][idx] %}
  {% if raw is none or (raw | string | trim) == '' %}
    {{ return({}) }}
  {% endif %}
  {{ return(fromjson(raw | string)) }}
{% endmacro %}


{% macro cortex_agent__set_alias(agent_name, alias, to_version=none, from_alias=none, dry_run=true) %}
  {# Single alias-move primitive over native versioning. Resolve the target
     version either from an explicit VERSION$N (to_version) or from the version
     another alias currently points at (from_alias). No spec change. Dry-run by
     default and sandbox-guarded. promote_alias/rollback_alias are thin wrappers. #}
  {% set resource = cortex_agent__get_agent(agent_name) %}
  {% set agent = cortex_agent__agent_meta(resource) %}
  {% set agent_fqn = cortex_agent__resource_agent_fqn(resource, agent) %}
  {% set alias = cortex_agent__unquoted_identifier(alias, 'alias') %}

  {% if not execute %}
    {{ return('') }}
  {% endif %}

  {% if to_version is not none %}
    {% if not modules.re.match('^VERSION\\$[1-9]\\d*$', to_version) %}
      {{ exceptions.raise_compiler_error("set_alias: to_version must look like VERSION$N, got '" ~ to_version ~ "'") }}
    {% endif %}
    {% set target_version = to_version %}
  {% elif from_alias is not none %}
    {% set from_alias = cortex_agent__unquoted_identifier(from_alias, 'source alias') %}
    {% set aliases = cortex_agent__describe_aliases(agent_fqn) %}
    {% set from_key = from_alias | upper %}
    {% if from_key not in aliases %}
      {{ exceptions.raise_compiler_error("set_alias: '" ~ from_alias ~ "' not set on " ~ agent_fqn ~ "; current: " ~ tojson(aliases)) }}
    {% endif %}
    {% set target_version = aliases[from_key] %}
  {% else %}
    {{ exceptions.raise_compiler_error("set_alias: provide either to_version or from_alias") }}
  {% endif %}

  {% set stmt = "ALTER AGENT " ~ agent_fqn ~ " MODIFY VERSION " ~ target_version ~ " SET ALIAS = " ~ alias %}

  {% if dry_run %}
    {% do log("[DRY RUN] set alias " ~ alias ~ " -> " ~ target_version ~ " on " ~ agent_fqn, info=True) %}
    {% do log(stmt, info=True) %}
    {{ return(target_version) }}
  {% endif %}

  {% do cortex_agent__assert_deploy_target('set_alias') %}
  {% do run_query(stmt) %}
  {% do log("Set alias " ~ alias ~ " -> " ~ target_version ~ " on " ~ agent_fqn, info=True) %}
  {{ return(target_version) }}
{% endmacro %}


{% macro cortex_agent__promote_alias(agent_name, from_alias, to_alias, dry_run=true) %}
  {# Move to_alias to whatever version currently holds from_alias. Thin wrapper. #}
  {{ return(cortex_agent__set_alias(agent_name, to_alias, from_alias=from_alias, dry_run=dry_run)) }}
{% endmacro %}


{% macro cortex_agent__rollback_alias(agent_name, alias, to_version, dry_run=true) %}
  {# Reassign alias to an explicit prior VERSION$N. Thin wrapper. #}
  {{ return(cortex_agent__set_alias(agent_name, alias, to_version=to_version, dry_run=dry_run)) }}
{% endmacro %}
