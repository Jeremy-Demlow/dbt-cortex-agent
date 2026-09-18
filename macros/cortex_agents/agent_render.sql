{% macro cortex_agent__unquoted_identifier(value, label='identifier') %}
  {% set text = value | string %}
  {% if not modules.re.match('^[A-Za-z_][A-Za-z0-9_$]*$', text) %}
    {{ exceptions.raise_compiler_error(label ~ " must be an unquoted Snowflake identifier, got '" ~ text ~ "'") }}
  {% endif %}
  {{ return(text | upper) }}
{% endmacro %}

{% macro cortex_agent__routing_alias(value, label='Agent alias') %}
  {% set safe_alias = dbt_cortex_agent.cortex_agent__unquoted_identifier(value, label) %}
  {% if safe_alias in ['DEFAULT', 'FIRST', 'LAST', 'LIVE'] %}
    {{ exceptions.raise_compiler_error(label ~ " is reserved for Snowflake routing: " ~ safe_alias) }}
  {% endif %}
  {{ return(safe_alias) }}
{% endmacro %}

{% macro cortex_agent__unquoted_fqn(value, label='object') %}
  {% set text = value | string %}
  {% set parts = text.split('.') %}
  {% if parts | length != 3 %}
    {{ exceptions.raise_compiler_error(label ~ " must be a three-part Snowflake identifier, got '" ~ text ~ "'") }}
  {% endif %}
  {% set safe_parts = [] %}
  {% for part in parts %}
    {% do safe_parts.append(dbt_cortex_agent.cortex_agent__unquoted_identifier(part, label ~ ' part')) %}
  {% endfor %}
  {{ return(safe_parts | join('.')) }}
{% endmacro %}

{% macro cortex_agent__resource_agent_fqn(resource, agent) %}
  {% set database_name = cortex_agent__unquoted_identifier(resource.database, 'database') %}
  {% set schema_name = cortex_agent__unquoted_identifier(resource.schema, 'schema') %}
  {% set agent_name = cortex_agent__unquoted_identifier(resource.alias or resource.name, 'Agent object') %}
  {{ return(database_name ~ '.' ~ schema_name ~ '.' ~ agent_name) }}
{% endmacro %}

{% macro cortex_agent__assert_staged_skills_ready(agent) %}
  {# Fail-closed guard for the mutating deploy path: every stage-sourced skill
     must have a SKILL.md before the full Agent specification is versioned. #}
  {% if not execute %}
    {{ return(none) }}
  {% endif %}
  {% set skills = agent.get('skills', agent.get('capabilities', {}).get('skills', [])) %}
  {% for skill in skills %}
    {% set source = skill.get('source', {}) %}
    {% if (source.get('type') | string | lower) == 'stage' %}
      {% set safe_path = dbt_cortex_agent.cortex_agent__stage_path(source.get('path'), "Skill '" ~ skill.get('name') ~ "' stage path") %}
      {% set ls_result = run_query("LIST " ~ safe_path ~ " PATTERN='.*SKILL[.]md'") %}
      {% if ls_result.rows | length == 0 %}
        {{ exceptions.raise_compiler_error("Refusing to deploy agent '" ~ agent.get('snowflake_name', '<agent>') ~ "': staged skill '" ~ skill.get('name') ~ "' has no SKILL.md at " ~ source.get('path') ~ ". Upload the declared skill with dbt-cortex-agent skill upload --apply, or set var('cortex_agent_validate_staged_skills', false) to override.") }}
      {% endif %}
    {% endif %}
  {% endfor %}
  {{ return(none) }}
{% endmacro %}

{% macro cortex_agent__debug_assert_skill_path(path) %}
  {# Behavioral test hook (read-only LIST, no mutation): run the fail-closed
     staged-skill readiness check against a synthetic single-skill agent pointed at
     `path`. Contract tests call this against a guaranteed-empty stage path to prove
     the guard rejects a dangling skill ref. #}
  {% set synthetic = {'snowflake_name': 'DEBUG_PROBE', 'capabilities': {'skills': [{'name': 'probe', 'source': {'type': 'stage', 'path': path}}]}} %}
  {% do cortex_agent__assert_staged_skills_ready(synthetic) %}
  {% do log('[OK] staged-skill path has SKILL.md: ' ~ path, info=True) %}
{% endmacro %}

{% macro cortex_agent__stage_path(value, label='stage path') %}
  {% set text = value | string %}
  {% if not modules.re.match('^@[A-Za-z_][A-Za-z0-9_$]*[.][A-Za-z_][A-Za-z0-9_$]*[.][A-Za-z_][A-Za-z0-9_$]*/[A-Za-z0-9_$.-]+(/[A-Za-z0-9_$.-]+)*$', text) %}
    {{ exceptions.raise_compiler_error(label ~ " must be an unquoted three-part internal stage path with a safe folder suffix, got '" ~ text ~ "'") }}
  {% endif %}
  {% set suffix = text.split('/', 1)[1] %}
  {% for part in suffix.split('/') %}
    {% if part in ['.', '..'] %}
      {{ exceptions.raise_compiler_error(label ~ " contains an unsafe folder component: '" ~ part ~ "'") }}
    {% endif %}
  {% endfor %}
  {{ return(text) }}
{% endmacro %}

{% macro cortex_agent__live_draft_exists(agent_fqn) %}
  {# A row with an empty version name in SHOW VERSIONS is the editable LIVE draft. #}
  {% if execute %}
    {% set results = run_query("SHOW VERSIONS IN AGENT " ~ agent_fqn) %}
    {% for row in results %}
      {% set version_name = row[1] %}
      {% if version_name is none or (version_name | string | trim) == '' %}
        {{ return(true) }}
      {% endif %}
    {% endfor %}
  {% endif %}
  {{ return(false) }}
{% endmacro %}

{% macro cortex_agent__agent_exists(agent_fqn) %}
  {% set parts = agent_fqn.split('.') %}
  {% set agent_name = parts[-1] %}
  {% set schema_fqn = parts[0] ~ '.' ~ parts[1] %}
  {% if execute %}
    {% set results = run_query("SHOW AGENTS IN SCHEMA " ~ schema_fqn) %}
    {% set col_names = results.column_names | map('lower') | list %}
    {% set name_idx = col_names.index('name') if 'name' in col_names else 1 %}
    {% for row in results %}
      {% if (row[name_idx] | upper) == (agent_name | upper) %}
        {{ return(true) }}
      {% endif %}
    {% endfor %}
  {% endif %}
  {{ return(false) }}
{% endmacro %}

{% macro cortex_agent__managed_version(agent_fqn, spec_hash, skill_hash='') %}
  {# Find the newest immutable version created from the requested content.
     DEFAULT may intentionally point backward after a rollback. #}
  {% if not execute %}
    {{ return(none) }}
  {% endif %}
  {% set results = run_query("SHOW VERSIONS IN AGENT " ~ agent_fqn) %}
  {% set col_names = results.column_names | map('lower') | list %}
  {% set name_idx = col_names.index('name') if 'name' in col_names else 1 %}
  {% if 'comment' not in col_names %}
    {{ return(none) }}
  {% endif %}
  {% set comment_idx = col_names.index('comment') %}
  {% set state = namespace(version=none, number=-1) %}
  {% for row in results %}
    {% set version_name = row[name_idx] | string %}
    {% set version_match = modules.re.match('^VERSION[$]([1-9][0-9]*)$', version_name) %}
    {% set comment = row[comment_idx] | string %}
    {% set spec_match = modules.re.search('spec_md5=([0-9a-f]+)', comment) %}
    {% set skill_match = modules.re.search('skill_md5=([0-9a-f]+)', comment) %}
    {% set row_skill_hash = skill_match.group(1) if skill_match else '' %}
    {% if version_match and spec_match and spec_match.group(1) == spec_hash and row_skill_hash == skill_hash %}
      {% set number = version_match.group(1) | int %}
      {% if number > state.number %}
        {% set state.number = number %}
        {% set state.version = version_name %}
      {% endif %}
    {% endif %}
  {% endfor %}
  {{ return(state.version) }}
{% endmacro %}

{% macro cortex_agent__skills_hash(agent) %}
  {# Skill content lives on the stage, not inside the agent spec JSON. Include a
     hash of staged skill files in deploy idempotency so editing SKILL.md mints
     a new agent version even when spec_md5 is unchanged. #}
  {% if not execute %}
    {{ return('') }}
  {% endif %}
  {% set entries = [] %}
  {% set skills = agent.get('skills', agent.get('capabilities', {}).get('skills', [])) %}
  {% for skill in skills %}
    {% set source = skill.get('source', {}) %}
    {% if (source.get('type') | string | lower) == 'stage' %}
      {% set safe_path = dbt_cortex_agent.cortex_agent__stage_path(source.get('path'), "Skill '" ~ skill.get('name') ~ "' stage path") %}
      {% set rows = run_query("LIST " ~ safe_path) %}
      {% for row in rows %}
        {% do entries.append((row[0] | string) ~ ':' ~ (row[1] | string) ~ ':' ~ (row[2] | string)) %}
      {% endfor %}
    {% endif %}
  {% endfor %}
  {% if entries | length == 0 %}
    {{ return('') }}
  {% endif %}
  {{ return(local_md5(entries | sort | join('|'))) }}
{% endmacro %}

{% macro cortex_agent__deploy_phase(agent_fqn, phase) %}
  {% do log('CORTEX_AGENT_DEPLOY_PHASE=' ~ tojson({'agent_fqn': agent_fqn, 'phase': phase}), info=True) %}
{% endmacro %}

{% macro cortex_agent__reconcile_live(agent_fqn) %}
  {% if not execute %}
    {{ return(none) }}
  {% endif %}
  {% set agent_fqn = dbt_cortex_agent.cortex_agent__unquoted_fqn(agent_fqn, 'Agent FQN') %}
  {% do dbt_cortex_agent.cortex_agent__assert_deploy_target('cortex_agent__reconcile_live') %}
  {% do dbt_cortex_agent.cortex_agent__assert_database_allowed('cortex_agent__reconcile_live', agent_fqn.split('.')[0]) %}
  {% if not dbt_cortex_agent.cortex_agent__live_draft_exists(agent_fqn) %}
    {% do run_query("ALTER AGENT " ~ agent_fqn ~ " ADD LIVE VERSION FROM LAST") %}
  {% endif %}
  {% if not dbt_cortex_agent.cortex_agent__live_draft_exists(agent_fqn) %}
    {{ exceptions.raise_compiler_error("Agent LIVE postcondition failed: " ~ agent_fqn) }}
  {% endif %}
  {% do dbt_cortex_agent.cortex_agent__deploy_phase(agent_fqn, 'live_reconciled') %}
{% endmacro %}

{% macro cortex_agent__assert_creation_complete(agent_fqn) %}
  {% set description = run_query("DESCRIBE AGENT " ~ agent_fqn) %}
  {% set columns = description.column_names | map('lower') | list %}
  {% if 'comment' not in columns or description.rows | length != 1 %}
    {{ exceptions.raise_compiler_error('Cannot inspect Agent creation metadata; explicit recovery required: ' ~ agent_fqn) }}
  {% endif %}
  {% set comment = description.rows[0][columns.index('comment')] %}
  {% if comment == 'Managed by dbt cortex_agent materialization' %}
    {% set versions = run_query("SHOW VERSIONS IN AGENT " ~ agent_fqn) %}
    {% set version_columns = versions.column_names | map('lower') | list %}
    {% if 'name' in version_columns and 'comment' in version_columns %}
      {% for row in versions %}
        {% if row[version_columns.index('name')] == 'VERSION$1' %}
          {% set metadata = row[version_columns.index('comment')] | string %}
          {% if modules.re.search('spec_md5=[0-9a-f]+(?:[ ]|$)', metadata) and modules.re.search('skill_md5=[0-9a-f]*(?:[ ]|$)', metadata) %}
            {{ return(none) }}
          {% endif %}
        {% endif %}
      {% endfor %}
    {% endif %}
    {{ exceptions.raise_compiler_error('Unfinished initial Agent creation; explicit recovery required before retry: ' ~ agent_fqn ~ '. Initial version content and historical staged skills are not established. Inspect native versions and retained skill evidence; do not invent hash metadata. force_agent_recreate does not bypass this guard.') }}
  {% endif %}
{% endmacro %}

{% macro cortex_agent__apply_deploy(agent_fqn, spec_json, deploy_alias, mcp_statements=[], skill_hash='', reconcile_alias=false) %}
  {% if not execute %}
    {{ return('') }}
  {% endif %}

  {# Fail-closed: this primitive mutates, so guard it directly rather than
     trusting the caller. #}
  {% do dbt_cortex_agent.cortex_agent__assert_deploy_target('cortex_agent__apply_deploy') %}
  {% set agent_parts = agent_fqn.split('.') %}
  {% if agent_parts | length != 3 %}
    {{ exceptions.raise_compiler_error('cortex_agent__apply_deploy requires a three-part Agent FQN') }}
  {% endif %}
  {% do dbt_cortex_agent.cortex_agent__assert_database_allowed('cortex_agent__apply_deploy', agent_parts[0]) %}
  {% if '$$' in spec_json %}
    {{ exceptions.raise_compiler_error("Rendered agent spec contains '$$' delimiter") }}
  {% endif %}

  {% set spec_hash = local_md5(spec_json) %}
  {% set existed = dbt_cortex_agent.cortex_agent__agent_exists(agent_fqn) %}
  {% if existed %}
    {% do dbt_cortex_agent.cortex_agent__assert_creation_complete(agent_fqn) %}
  {% endif %}

  {# Idempotency: skip minting a new version when a managed immutable version
     matches the requested content, regardless of the serving DEFAULT.
     Skill content hash participates in the skip check because skills live on
     the stage, outside the spec JSON. MCP attach state is still not represented
     (MCP is DDL, not spec), so to (re)attach MCP on an unchanged spec+skill,
     use force_agent_recreate=true. #}
  {% if existed and not var('force_agent_recreate', false) %}
    {% set managed_version = dbt_cortex_agent.cortex_agent__managed_version(agent_fqn, spec_hash, skill_hash) %}
    {% if managed_version %}
      {% set aliases = dbt_cortex_agent.cortex_agent__describe_aliases(agent_fqn) %}
      {% set alias_key = deploy_alias | upper %}
      {% set expected_alias_version = aliases.get(alias_key, '') %}
      {% if reconcile_alias and expected_alias_version != managed_version %}
        {% do dbt_cortex_agent.cortex_agent__route_alias_for_fqn(agent_fqn, managed_version, deploy_alias, expected_alias_version) %}
        {% do dbt_cortex_agent.cortex_agent__deploy_phase(agent_fqn, 'alias_reconciled') %}
        {% do log("Reconciled alias " ~ deploy_alias ~ " -> " ~ managed_version ~ " on unchanged " ~ agent_fqn, info=True) %}
      {% endif %}
      {% do dbt_cortex_agent.cortex_agent__reconcile_live(agent_fqn) %}
      {% do log("No spec/skill change for " ~ agent_fqn ~ " (spec_md5=" ~ spec_hash ~ ", skill_md5=" ~ skill_hash ~ "); skipping COMMIT. Set var('force_agent_recreate', true) to force a new version.", info=True) %}
      {{ return(agent_fqn) }}
    {% endif %}
  {% endif %}

  {% if not existed %}
    {% do run_query("CREATE AGENT " ~ agent_fqn ~ " COMMENT = 'Managed by dbt cortex_agent materialization' FROM SPECIFICATION $$" ~ spec_json ~ "$$") %}
    {% set aliases = dbt_cortex_agent.cortex_agent__describe_aliases(agent_fqn) %}
    {% set new_version = aliases.get('DEFAULT') %}
    {% if not new_version %}
      {{ exceptions.raise_compiler_error("Created Agent has no DEFAULT immutable version: " ~ agent_fqn) }}
    {% endif %}
  {% else %}
    {% if not dbt_cortex_agent.cortex_agent__live_draft_exists(agent_fqn) %}
      {% do run_query("ALTER AGENT " ~ agent_fqn ~ " ADD LIVE VERSION FROM LAST") %}
    {% endif %}
    {% do run_query("ALTER AGENT " ~ agent_fqn ~ " MODIFY LIVE VERSION SET SPECIFICATION = $$" ~ spec_json ~ "$$") %}
    {% set version_comment = target.name ~ ' | inv=' ~ invocation_id ~ ' | spec_md5=' ~ spec_hash ~ ' | skill_md5=' ~ skill_hash %}
    {% set commit_result = run_query("ALTER AGENT " ~ agent_fqn ~ " COMMIT COMMENT = $$" ~ version_comment ~ "$$") %}
    {% set commit_msg = commit_result.rows[0][0] | string if commit_result.rows else '' %}
    {% set version_match = modules.re.search('VERSION\\$\\d+', commit_msg) %}
    {% if not version_match %}
      {{ exceptions.raise_compiler_error("Could not parse committed version from COMMIT result: " ~ commit_msg) }}
    {% endif %}
    {% set new_version = version_match.group(0) %}
  {% endif %}
  {% do dbt_cortex_agent.cortex_agent__deploy_phase(agent_fqn, 'version_committed') %}

  {% set version_comment = target.name ~ ' | inv=' ~ invocation_id ~ ' | spec_md5=' ~ spec_hash ~ ' | skill_md5=' ~ skill_hash %}
  {% do run_query("ALTER AGENT " ~ agent_fqn ~ " MODIFY VERSION " ~ new_version ~ " SET COMMENT = $$" ~ version_comment ~ "$$") %}
  {% do dbt_cortex_agent.cortex_agent__deploy_phase(agent_fqn, 'metadata_reconciled') %}
  {% set current_aliases = dbt_cortex_agent.cortex_agent__describe_aliases(agent_fqn) %}
  {% set expected_alias_version = current_aliases.get(deploy_alias | upper, '') %}
  {% do dbt_cortex_agent.cortex_agent__route_alias_for_fqn(agent_fqn, new_version, deploy_alias, expected_alias_version) %}
  {% do dbt_cortex_agent.cortex_agent__deploy_phase(agent_fqn, 'alias_reconciled') %}

  {% do dbt_cortex_agent.cortex_agent__reconcile_live(agent_fqn) %}

  {# MCP connectors reference a pre-existing EXTERNAL MCP SERVER object and are
     attached out-of-band from the spec. Gated behind mcp_deploy_enabled because
     the external server must already exist (OAuth-backed). #}
  {% if mcp_statements | length > 0 %}
    {% if var('mcp_deploy_enabled', false) %}
      {% for stmt in mcp_statements %}
        {% do run_query(stmt) %}
        {% do log("Attached MCP connector: " ~ stmt, info=True) %}
      {% endfor %}
    {% else %}
      {% do log("[INFO] " ~ (mcp_statements | length) ~ " MCP connector attach(es) skipped; set var('mcp_deploy_enabled', true) once the EXTERNAL MCP SERVER object exists.", info=True) %}
    {% endif %}
  {% endif %}

  {% do log("Deployed " ~ agent_fqn ~ " (" ~ new_version ~ ", alias=" ~ deploy_alias ~ ", first_deploy=" ~ (not existed) ~ ")", info=True) %}
  {{ return(agent_fqn) }}
{% endmacro %}
