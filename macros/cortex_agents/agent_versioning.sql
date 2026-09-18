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

{% macro cortex_agent__version_state(agent_fqn) %}
  {% set safe_fqn = dbt_cortex_agent.cortex_agent__unquoted_fqn(agent_fqn, 'Agent FQN') %}
  {% set state = {'agent_fqn': safe_fqn, 'exists': false, 'versions': [], 'aliases': {}, 'default_version': none, 'last_version': none, 'live': false} %}
  {% if not execute or not dbt_cortex_agent.cortex_agent__agent_exists(safe_fqn) %}
    {{ return(state) }}
  {% endif %}
  {% set aliases = dbt_cortex_agent.cortex_agent__describe_aliases(safe_fqn) %}
  {% set rows = run_query("SHOW VERSIONS IN AGENT " ~ safe_fqn) %}
  {% set columns = rows.column_names | map('lower') | list %}
  {% set name_idx = columns.index('name') if 'name' in columns else 1 %}
  {% set version_numbers = [] %}
  {% set live_state = namespace(present=false) %}
  {% for row in rows %}
    {% set name = row[name_idx] | string %}
    {% set match = modules.re.match('^VERSION[$]([1-9][0-9]*)$', name) %}
    {% if match %}
      {% do version_numbers.append(match.group(1) | int) %}
    {% elif name | trim == '' %}
      {% set live_state.present = true %}
    {% endif %}
  {% endfor %}
  {% do version_numbers.sort() %}
  {% set versions = [] %}
  {% for number in version_numbers %}
    {% do versions.append('VERSION$' ~ number) %}
  {% endfor %}
  {% do state.update({
    'exists': true,
    'versions': versions,
    'aliases': aliases,
    'default_version': aliases.get('DEFAULT'),
    'last_version': aliases.get('LAST'),
    'live': live_state.present
  }) %}
  {{ return(state) }}
{% endmacro %}

{% macro cortex_agent__version_state_for_model(agent_name) %}
  {% set resource = dbt_cortex_agent.cortex_agent__get_agent(agent_name) %}
  {% set agent_fqn = dbt_cortex_agent.cortex_agent__resource_agent_fqn(resource, dbt_cortex_agent.cortex_agent__agent_meta(resource)) %}
  {% set state = dbt_cortex_agent.cortex_agent__version_state(agent_fqn) %}
  {% do log('CORTEX_AGENT_VERSION_STATE=' ~ tojson(state), info=True) %}
  {{ return(tojson(state)) }}
{% endmacro %}

{% macro cortex_agent__assert_expected_identity(agent_fqn, expected_agent_fqn=none) %}
  {% set safe_fqn = dbt_cortex_agent.cortex_agent__unquoted_fqn(agent_fqn, 'Agent FQN') %}
  {% if expected_agent_fqn is not none %}
    {% set expected_fqn = dbt_cortex_agent.cortex_agent__unquoted_fqn(expected_agent_fqn, 'expected Agent FQN') %}
    {% if safe_fqn != expected_fqn %}
      {{ exceptions.raise_compiler_error('Agent identity changed after planning: expected ' ~ expected_fqn ~ ', resolved ' ~ safe_fqn) }}
    {% endif %}
  {% endif %}
  {{ return(safe_fqn) }}
{% endmacro %}

{% macro cortex_agent__route_alias_for_fqn(agent_fqn, to_version, alias, expected_alias_version='', expected_agent_fqn=none) %}
  {% set agent_fqn = dbt_cortex_agent.cortex_agent__assert_expected_identity(agent_fqn, expected_agent_fqn) %}
  {% set safe_version = to_version | string | upper %}
  {% if not modules.re.match('^VERSION[$][1-9][0-9]*$', safe_version) %}
    {{ exceptions.raise_compiler_error("to_version must look like VERSION$N") }}
  {% endif %}
  {% set safe_alias = dbt_cortex_agent.cortex_agent__routing_alias(alias, 'Agent alias') %}
  {% set before = dbt_cortex_agent.cortex_agent__version_state(agent_fqn) %}
  {% if not before.get('exists') or safe_version not in before.get('versions', []) %}
    {{ exceptions.raise_compiler_error("Agent version does not exist: " ~ agent_fqn ~ '!' ~ safe_version) }}
  {% endif %}
  {% set previous_alias_version = before.get('aliases', {}).get(safe_alias) %}
  {% set expected_version = expected_alias_version | string | upper %}
  {% if (previous_alias_version or '') != expected_version %}
    {{ exceptions.raise_compiler_error("Agent alias changed after planning for " ~ safe_alias) }}
  {% endif %}
  {% if previous_alias_version and previous_alias_version != safe_version %}
    {% do dbt_cortex_agent.cortex_agent__assert_expected_identity(agent_fqn, expected_agent_fqn) %}
    {% do run_query("ALTER AGENT " ~ agent_fqn ~ " MODIFY VERSION " ~ previous_alias_version ~ " UNSET ALIAS") %}
  {% endif %}
  {% if previous_alias_version != safe_version %}
    {% do dbt_cortex_agent.cortex_agent__assert_expected_identity(agent_fqn, expected_agent_fqn) %}
    {% do run_query("ALTER AGENT " ~ agent_fqn ~ " MODIFY VERSION " ~ safe_version ~ " SET ALIAS = " ~ safe_alias) %}
  {% endif %}
  {% set after = dbt_cortex_agent.cortex_agent__version_state(agent_fqn) %}
  {% if after.get('aliases', {}).get(safe_alias) != safe_version %}
    {{ exceptions.raise_compiler_error("Agent alias postcondition failed for " ~ safe_alias) }}
  {% endif %}
  {% set result = {'agent_fqn': agent_fqn, 'to_version': safe_version, 'alias': safe_alias, 'set_default': false, 'before': before, 'after': after} %}
  {% do log('CORTEX_AGENT_ROUTE_RESULT=' ~ tojson(result), info=True) %}
  {{ return(tojson(result)) }}
{% endmacro %}

{% macro cortex_agent__route_alias(agent_name, to_version, alias, expected_alias_version='', expected_agent_fqn=none) %}
  {% do dbt_cortex_agent.cortex_agent__assert_deploy_target('cortex_agent__route_alias') %}
  {% set resource = dbt_cortex_agent.cortex_agent__get_agent(agent_name) %}
  {% set agent_fqn = dbt_cortex_agent.cortex_agent__resource_agent_fqn(resource, dbt_cortex_agent.cortex_agent__agent_meta(resource)) %}
  {% set parts = agent_fqn.split('.') %}
  {% do dbt_cortex_agent.cortex_agent__assert_database_allowed('cortex_agent__route_alias', parts[0]) %}
  {{ return(dbt_cortex_agent.cortex_agent__route_alias_for_fqn(agent_fqn, to_version, alias, expected_alias_version, expected_agent_fqn)) }}
{% endmacro %}

{% macro cortex_agent__route_default(agent_name, to_version, expected_default_version, expected_agent_fqn=none) %}
  {% do dbt_cortex_agent.cortex_agent__assert_deploy_target('cortex_agent__route_default') %}
  {% set resource = dbt_cortex_agent.cortex_agent__get_agent(agent_name) %}
  {% set agent_fqn = dbt_cortex_agent.cortex_agent__resource_agent_fqn(resource, dbt_cortex_agent.cortex_agent__agent_meta(resource)) %}
  {% set parts = agent_fqn.split('.') %}
  {% do dbt_cortex_agent.cortex_agent__assert_database_allowed('cortex_agent__route_default', parts[0]) %}
  {% set agent_fqn = dbt_cortex_agent.cortex_agent__assert_expected_identity(agent_fqn, expected_agent_fqn) %}
  {% set safe_version = to_version | string | upper %}
  {% if not modules.re.match('^VERSION[$][1-9][0-9]*$', safe_version) %}
    {{ exceptions.raise_compiler_error("to_version must look like VERSION$N") }}
  {% endif %}
  {% set before = dbt_cortex_agent.cortex_agent__version_state(agent_fqn) %}
  {% if not before.get('exists') or safe_version not in before.get('versions', []) %}
    {{ exceptions.raise_compiler_error("Agent version does not exist: " ~ agent_fqn ~ '!' ~ safe_version) }}
  {% endif %}
  {% set expected_version = expected_default_version | string | upper %}
  {% if (before.get('default_version') or '') != expected_version %}
    {{ exceptions.raise_compiler_error("Agent DEFAULT changed after alias routing") }}
  {% endif %}
  {% if before.get('default_version') != safe_version %}
    {% do dbt_cortex_agent.cortex_agent__assert_expected_identity(agent_fqn, expected_agent_fqn) %}
    {% do run_query("ALTER AGENT " ~ agent_fqn ~ " SET DEFAULT_VERSION = '" ~ safe_version ~ "'") %}
  {% endif %}
  {% set after = dbt_cortex_agent.cortex_agent__version_state(agent_fqn) %}
  {% if after.get('default_version') != safe_version %}
    {{ exceptions.raise_compiler_error("Agent DEFAULT postcondition failed") }}
  {% endif %}
  {% set result = {'agent_fqn': agent_fqn, 'to_version': safe_version, 'before': before, 'after': after} %}
  {% do log('CORTEX_AGENT_DEFAULT_ROUTE_RESULT=' ~ tojson(result), info=True) %}
  {{ return(tojson(result)) }}
{% endmacro %}

{% macro cortex_agent__route_version(agent_name, to_version, alias, set_default=false, expected_agent_fqn=none) %}
  {% set before_json = dbt_cortex_agent.cortex_agent__version_state_for_model(agent_name) %}
  {% set before = fromjson(before_json) %}
  {% set expected_alias_version = before.get('aliases', {}).get(alias | string | upper, '') %}
  {% set alias_result = dbt_cortex_agent.cortex_agent__route_alias(agent_name, to_version, alias, expected_alias_version, expected_agent_fqn) %}
  {% if set_default %}
    {% set default_result = dbt_cortex_agent.cortex_agent__route_default(agent_name, to_version, before.get('default_version', ''), expected_agent_fqn) %}
  {% endif %}
  {{ return(alias_result) }}
{% endmacro %}

{% macro cortex_agent__drop(agent_name, expected_agent_fqn=none) %}
  {% do dbt_cortex_agent.cortex_agent__assert_deploy_target('cortex_agent__drop') %}
  {% set resource = dbt_cortex_agent.cortex_agent__get_agent(agent_name) %}
  {% set agent_fqn = dbt_cortex_agent.cortex_agent__resource_agent_fqn(resource, dbt_cortex_agent.cortex_agent__agent_meta(resource)) %}
  {% set parts = agent_fqn.split('.') %}
  {% do dbt_cortex_agent.cortex_agent__assert_database_allowed('cortex_agent__drop', parts[0]) %}
  {% set agent_fqn = dbt_cortex_agent.cortex_agent__assert_expected_identity(agent_fqn, expected_agent_fqn) %}
  {% set before = dbt_cortex_agent.cortex_agent__version_state(agent_fqn) %}
  {% do dbt_cortex_agent.cortex_agent__assert_expected_identity(agent_fqn, expected_agent_fqn) %}
  {% set evidence = {'agent_fqn': agent_fqn, 'dropped': none, 'before': before, 'after': none, 'drop_status': 'unknown'} %}
  {% do log('CORTEX_AGENT_DROP_EVIDENCE=' ~ tojson(evidence), info=True) %}
  {% do run_query("DROP AGENT IF EXISTS " ~ agent_fqn) %}
  {% do evidence.update({'dropped': before.get('exists'), 'drop_status': 'completed'}) %}
  {% do log('CORTEX_AGENT_DROP_EVIDENCE=' ~ tojson(evidence), info=True) %}
  {% set after = dbt_cortex_agent.cortex_agent__version_state(agent_fqn) %}
  {% do evidence.update({'after': after}) %}
  {% do log('CORTEX_AGENT_DROP_EVIDENCE=' ~ tojson(evidence), info=True) %}
  {% if after.get('exists') %}
    {{ exceptions.raise_compiler_error("Agent drop postcondition failed: " ~ agent_fqn) }}
  {% endif %}
  {% set result = {'agent_fqn': agent_fqn, 'dropped': before.get('exists'), 'before': before, 'after': after} %}
  {% do log('CORTEX_AGENT_DROP_RESULT=' ~ tojson(result), info=True) %}
  {{ return(tojson(result)) }}
{% endmacro %}
