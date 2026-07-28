{% macro cortex_agent__not_eval_supported(value) %}
  {{ return(value is sameas false or (value | string | lower) == 'false') }}
{% endmacro %}

{% macro cortex_agent__target_agent_name(agent, projection='canonical') %}
  {% set naming = agent.get('naming', {}) %}
  {% set explicit = naming.get(target.name) %}
  {% if explicit %}
    {% set base_name = explicit | upper %}
  {% else %}
    {% set base_name = agent.get('snowflake_name') | upper %}
    {% set env_suffixes = var('cortex_agent_env_suffixes', {'dev': '_DEV', 'dbt_focus': '_DBT_FOCUS'}) %}
    {% set suffix = env_suffixes.get(target.name, '') %}
    {% if suffix and not base_name.endswith(suffix) %}
      {% set base_name = base_name ~ suffix %}
    {% endif %}
  {% endif %}
  {% set eval_suffix = var('cortex_agent_eval_suffix', '_EVAL') %}
  {% if projection == 'native_eval' and not base_name.endswith(eval_suffix) %}
    {% set base_name = base_name ~ eval_suffix %}
  {% endif %}
  {{ return(base_name) }}
{% endmacro %}

{% macro cortex_agent__target_agent_fqn(agent, projection='canonical') %}
  {% set database_name = target.database %}
  {% set schema_name = cortex_agent__schema() %}
  {% set agent_name = cortex_agent__target_agent_name(agent, projection) %}
  {{ return(database_name ~ '.' ~ schema_name ~ '.' ~ agent_name) }}
{% endmacro %}

{% macro cortex_agent__deploy_alias(agent) %}
  {% set versioning = agent.get('versioning', {}) %}
  {% set env_versioning = versioning.get(target.name, {}) %}
  {{ return(env_versioning.get('deploy_alias', 'latest')) }}
{% endmacro %}

{% macro cortex_agent__render_tool(tool, projection='canonical') %}
  {# Render one declared tool into {spec_entry, resource_key, resource}. Returns
     none when the native-eval projection excludes the tool. resource is none for
     tool types that carry no tool_resources entry. #}
  {% if projection == 'native_eval' and cortex_agent__not_eval_supported(tool.get('evaluation_supported')) %}
    {% do log("[INFO] Native-eval projection: skipping tool '" ~ tool.get('name') ~ "' because evaluation_supported=false", info=True) %}
    {{ return(none) }}
  {% endif %}

  {% set spec_entry = {
    'tool_spec': {
      'type': tool.get('type'),
      'name': tool.get('name'),
      'description': tool.get('description') | trim
    }
  } %}

  {% set execution_environment = {
    'type': 'warehouse',
    'warehouse': tool.get('warehouse', target.warehouse),
    'query_timeout': tool.get('query_timeout', 300)
  } %}

  {% set resource = none %}
  {% if tool.get('type') == 'cortex_analyst_text_to_sql' %}
    {% set resource = {
      'semantic_view': cortex_agent__semantic_view_fqn(tool.get('semantic_view_model')),
      'execution_environment': execution_environment
    } %}
  {% elif tool.get('type') == 'cortex_search' %}
    {% set resource = {
      'search_service': tool.get('search_service'),
      'execution_environment': execution_environment
    } %}
  {% elif tool.get('type') == 'generic' %}
    {% set resource = {
      'type': 'procedure',
      'identifier': tool.get('identifier'),
      'execution_environment': execution_environment
    } %}
  {% endif %}

  {{ return({'spec_entry': spec_entry, 'resource_key': tool.get('name'), 'resource': resource}) }}
{% endmacro %}

{% macro cortex_agent__render_capabilities(caps, projection='canonical') %}
  {# Render capability-level tools (web_search, data_to_chart, code_execution)
     and top-level skills into {tools, resources, skills}. The native-eval
     projection excludes skills (built-in EXECUTE_AI_EVALUATION does not support
     them); MCP is attached via DDL, not the spec, so it is handled separately. #}
  {% set tools = [] %}
  {% set resources = {} %}
  {% set skills_out = [] %}

  {% set skills = caps.get('skills', []) %}
  {% if skills | length > 0 %}
    {% if projection == 'native_eval' %}
      {% do log("[INFO] Native-eval projection: skills are declared in canonical metadata but are excluded from built-in EXECUTE_AI_EVALUATION: " ~ (skills | map(attribute='name') | join(', ')), info=True) %}
    {% else %}
      {% for skill in skills %}
        {% set source = skill.get('source', {}) %}
        {% set skill_source = {'type': (source.get('type') | string | upper), 'path': source.get('path')} %}
        {# SQL agent specifications accept name+source for skills; description
           is read from SKILL.md at the referenced source path. #}
        {% do skills_out.append({'name': skill.get('name'), 'source': skill_source}) %}
      {% endfor %}
    {% endif %}
  {% endif %}

  {% set web = caps.get('web_search', {}) %}
  {% if web.get('enabled') %}
    {% do tools.append({'tool_spec': {'type': 'web_search', 'name': 'web_search'}}) %}
    {% if web.get('max_results') is not none %}
      {% do resources.update({'web_search': {'max_results': web.get('max_results')}}) %}
    {% endif %}
  {% endif %}

  {% set chart = caps.get('data_to_chart', {}) %}
  {% if chart.get('enabled') %}
    {% do tools.append({'tool_spec': {
      'type': 'data_to_chart',
      'name': 'data_to_chart',
      'description': chart.get('description', 'Generates visualizations from data')
    }}) %}
  {% endif %}

  {% set code_exec = caps.get('code_execution', {}) %}
  {% if code_exec.get('enabled') and var('code_execution_enabled', false) and not (projection == 'native_eval' and cortex_agent__not_eval_supported(code_exec.get('evaluation_supported'))) %}
    {% do tools.append({'tool_spec': {'type': 'code_execution', 'name': 'code_execution'}}) %}
    {% set code_res = {} %}
    {% if code_exec.get('artifact_repositories') %}
      {% do code_res.update({'artifact_repositories': code_exec.get('artifact_repositories')}) %}
    {% endif %}
    {% if code_exec.get('external_access_integrations') %}
      {% do code_res.update({'external_access_integrations': code_exec.get('external_access_integrations')}) %}
    {% endif %}
    {% do resources.update({'code_execution': code_res}) %}
  {% elif projection == 'native_eval' and code_exec.get('enabled') and cortex_agent__not_eval_supported(code_exec.get('evaluation_supported')) %}
    {% do log("[INFO] Native-eval projection: skipping capability 'code_execution' because evaluation_supported=false", info=True) %}
  {% elif code_exec.get('enabled') and not var('code_execution_enabled', false) %}
    {% do log("[INFO] code_execution is declared but not rendered because var('code_execution_enabled') is false", info=True) %}
  {% endif %}

  {{ return({'tools': tools, 'resources': resources, 'skills': skills_out}) }}
{% endmacro %}

{% macro cortex_agent__render_instructions(agent) %}
  {# Build the instructions block (orchestration/response/sample_questions). #}
  {% set instructions = agent.get('instructions', {}) %}
  {% set sample_questions = [] %}
  {% for question in agent.get('sample_questions', []) %}
    {% do sample_questions.append({'question': question}) %}
  {% endfor %}
  {{ return({
    'orchestration': instructions.get('orchestration', '') | trim,
    'response': instructions.get('response', '') | trim,
    'sample_questions': sample_questions
  }) }}
{% endmacro %}

{% macro cortex_agent__build_spec(agent_name, projection='canonical') %}
  {# Compose the deployable spec from single-responsibility renderers. Output is
     insertion-order stable: declared tools (YAML order) then capability tools;
     tool_resources follow the same order. #}
  {% do cortex_agent__validate(agent_name, projection) %}
  {% set exposure = cortex_agent__get_agent(agent_name) %}
  {% set agent = exposure.meta.get('cortex_agent', {}) %}
  {% set tools = [] %}
  {% set tool_resources = {} %}

  {% for tool in agent.get('tools', []) %}
    {% set rendered = cortex_agent__render_tool(tool, projection) %}
    {% if rendered is not none %}
      {% do tools.append(rendered.spec_entry) %}
      {% if rendered.resource is not none %}
        {% do tool_resources.update({rendered.resource_key: rendered.resource}) %}
      {% endif %}
    {% endif %}
  {% endfor %}

  {% set capabilities = cortex_agent__render_capabilities(agent.get('capabilities', {}), projection) %}
  {% do tools.extend(capabilities.tools) %}
  {% do tool_resources.update(capabilities.resources) %}

  {% set spec = {
    'models': {'orchestration': agent.get('model', {}).get('orchestration', var('cortex_agent_default_model', 'claude-sonnet-4-5'))},
    'orchestration': {'budget': agent.get('orchestration', {}).get('budget', {'seconds': 300, 'tokens': 50000})},
    'instructions': cortex_agent__render_instructions(agent),
    'tools': tools,
    'tool_resources': tool_resources
  } %}

  {% if capabilities.skills | length > 0 %}
    {% do spec.update({'skills': capabilities.skills}) %}
  {% endif %}

  {{ return(spec) }}
{% endmacro %}

{% macro cortex_agent__render_mcp_ddl(agent, agent_fqn, projection='canonical') %}
  {# MCP connectors are attached with ALTER AGENT ... ADD MCP_SERVER (not the
     spec JSON) and reference a pre-existing EXTERNAL MCP SERVER object. Returns
     the DDL statements for enabled connectors in the canonical render; empty for
     the native-eval projection (built-in evals do not support MCP). #}
  {% set statements = [] %}
  {% if projection != 'native_eval' %}
    {% for connector in agent.get('capabilities', {}).get('mcp_connectors', []) %}
      {% if connector.get('enabled') %}
        {% do statements.append("ALTER AGENT " ~ agent_fqn ~ " ADD MCP_SERVER = '" ~ connector.get('server') ~ "'") %}
      {% endif %}
    {% endfor %}
  {% endif %}
  {{ return(statements) }}
{% endmacro %}

{% macro cortex_agent__render_spec(agent_name, projection='canonical') %}
  {% set spec = cortex_agent__build_spec(agent_name, projection) %}
  {% do log(tojson(spec), info=True) %}
  {{ return(tojson(spec)) }}
{% endmacro %}

{% macro cortex_agent__deploy(agent_name, projection='canonical', dry_run=True, alias=None) %}
  {% set exposure = cortex_agent__get_agent(agent_name) %}
  {% set agent = exposure.meta.get('cortex_agent', {}) %}
  {% set spec = cortex_agent__build_spec(agent_name, projection) %}
  {% set spec_json = tojson(spec) %}
  {% set agent_fqn = cortex_agent__target_agent_fqn(agent, projection) %}
  {% set deploy_alias = alias or cortex_agent__deploy_alias(agent) %}
  {% set mcp_statements = cortex_agent__render_mcp_ddl(agent, agent_fqn, projection) %}

  {% if '$$' in spec_json %}
    {{ exceptions.raise_compiler_error("Rendered agent spec contains '$$' delimiter") }}
  {% endif %}

  {% set ddl %}
-- Native Cortex Agent versioning deploy (applied path branches on current state).
-- See docs/dbt_native_agent_eval_walkthrough.md for the full annotated sequence.
-- First deploy: CREATE AGENT (auto VERSION$1 + LIVE draft) -> MODIFY LIVE SET SPEC
--   -> COMMIT (VERSION$N, DEFAULT auto-advances) -> MODIFY VERSION SET ALIAS -> ADD LIVE FROM LAST.
-- Re-deploy: ADD LIVE FROM LAST -> MODIFY LIVE SET SPEC -> COMMIT -> SET ALIAS -> ADD LIVE FROM LAST.
CREATE AGENT IF NOT EXISTS {{ agent_fqn }} COMMENT = 'Managed by dbt cortex_agent__deploy (sandbox)';
ALTER AGENT {{ agent_fqn }} MODIFY LIVE VERSION SET SPECIFICATION = $$<spec_json, logged separately>$$;
ALTER AGENT {{ agent_fqn }} COMMIT;
ALTER AGENT {{ agent_fqn }} MODIFY VERSION <committed VERSION$N> SET ALIAS = {{ deploy_alias }};
ALTER AGENT {{ agent_fqn }} ADD LIVE VERSION FROM LAST;
  {% endset %}

  {% if dry_run %}
    {% do log("[DRY RUN] would deploy " ~ agent_fqn ~ " (projection=" ~ projection ~ ", alias=" ~ deploy_alias ~ ")", info=True) %}
    {% do log(ddl | trim, info=True) %}
    {% for stmt in mcp_statements %}
      {% do log("[DRY RUN] would attach MCP connector: " ~ stmt, info=True) %}
    {% endfor %}
    {% do log("Generated spec JSON:", info=True) %}
    {% do log(spec_json, info=True) %}
    {{ return(ddl | trim) }}
  {% else %}
    {% do cortex_agent__assert_deploy_target('cortex_agent__deploy') %}
    {# Fail-closed by construction: a mutating deploy must never mint a version
       whose spec references a staged skill missing from the stage. On by default
       here; var('cortex_agent_validate_staged_skills', false) is the escape hatch. #}
    {% if var('cortex_agent_validate_staged_skills', true) %}
      {% do cortex_agent__assert_staged_skills_ready(agent, projection) %}
    {% else %}
      {% do log("[WARN] staged-skill readiness check skipped via var('cortex_agent_validate_staged_skills', false) escape hatch", info=True) %}
    {% endif %}
    {% set skill_hash = cortex_agent__skills_hash(agent, projection) %}
    {{ return(cortex_agent__apply_deploy(agent_fqn, spec_json, deploy_alias, mcp_statements, skill_hash)) }}
  {% endif %}
{% endmacro %}

{% macro cortex_agent__assert_staged_skills_ready(agent, projection='canonical') %}
  {# Fail-closed guard for the mutating deploy path: every canonical, stage-sourced
     skill must have a SKILL.md present on the stage before we mint an agent version
     that references it. Raises a compiler error naming the agent, skill, and path
     when the stage path has no SKILL.md. Returns immediately (no remote call) for
     the native-eval projection or when execute is false, so render/preview stays
     offline (Factory Convention: render-never-requires-remote-state). #}
  {% if projection == 'native_eval' or not execute %}
    {{ return(none) }}
  {% endif %}
  {% for skill in agent.get('capabilities', {}).get('skills', []) %}
    {% set source = skill.get('source', {}) %}
    {% if (source.get('type') | string | lower) == 'stage' %}
      {% set ls_result = run_query("LIST " ~ source.get('path') ~ " PATTERN='.*SKILL[.]md'") %}
      {% if ls_result.rows | length == 0 %}
        {{ exceptions.raise_compiler_error("Refusing to deploy agent '" ~ agent.get('snowflake_name', '<agent>') ~ "': staged skill '" ~ skill.get('name') ~ "' has no SKILL.md at " ~ source.get('path') ~ ". Deploy the skill first (make dbt-focus-skill-deploy) or set var('cortex_agent_validate_staged_skills', false) to override.") }}
      {% endif %}
    {% endif %}
  {% endfor %}
  {{ return(none) }}
{% endmacro %}

{% macro cortex_agent__debug_assert_skill_path(path) %}
  {# Behavioral test hook (read-only LIST, no mutation): run the fail-closed
     staged-skill readiness check against a synthetic single-skill agent pointed at
     `path`. The dbt-focus-deploy-empty-skill-guard Make target calls this against a
     guaranteed-empty stage path to prove the guard rejects a dangling skill ref. #}
  {% set synthetic = {'snowflake_name': 'DEBUG_PROBE', 'capabilities': {'skills': [{'name': 'probe', 'source': {'type': 'stage', 'path': path}}]}} %}
  {% do cortex_agent__assert_staged_skills_ready(synthetic, 'canonical') %}
  {% do log('[OK] staged-skill path has SKILL.md: ' ~ path, info=True) %}
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

{% macro cortex_agent__current_spec_hash(agent_fqn) %}
  {# Read the spec_md5 stamped into the DEFAULT version's comment by a prior
     deploy. Returns none when the agent/version/hash is absent. Enables
     idempotent deploys (skip COMMIT when the rendered spec is unchanged). #}
  {% if not execute %}
    {{ return(none) }}
  {% endif %}
  {% set aliases = cortex_agent__describe_aliases(agent_fqn) %}
  {% set default_version = aliases.get('DEFAULT') %}
  {% if not default_version %}
    {{ return(none) }}
  {% endif %}
  {% set results = run_query("SHOW VERSIONS IN AGENT " ~ agent_fqn) %}
  {% set col_names = results.column_names | map('lower') | list %}
  {% set name_idx = col_names.index('name') if 'name' in col_names else 1 %}
  {% if 'comment' not in col_names %}
    {{ return(none) }}
  {% endif %}
  {% set comment_idx = col_names.index('comment') %}
  {% for row in results %}
    {% if (row[name_idx] | string) == default_version %}
      {% set comment = row[comment_idx] | string %}
      {% set match = modules.re.search('spec_md5=([0-9a-f]+)', comment) %}
      {% if match %}
        {{ return(match.group(1)) }}
      {% endif %}
    {% endif %}
  {% endfor %}
  {{ return(none) }}
{% endmacro %}

{% macro cortex_agent__current_deploy_hashes(agent_fqn) %}
  {% if not execute %}
    {{ return({}) }}
  {% endif %}
  {% set aliases = cortex_agent__describe_aliases(agent_fqn) %}
  {% set default_version = aliases.get('DEFAULT') %}
  {% if not default_version %}
    {{ return({}) }}
  {% endif %}
  {% set results = run_query("SHOW VERSIONS IN AGENT " ~ agent_fqn) %}
  {% set col_names = results.column_names | map('lower') | list %}
  {% set name_idx = col_names.index('name') if 'name' in col_names else 1 %}
  {% if 'comment' not in col_names %}
    {{ return({}) }}
  {% endif %}
  {% set comment_idx = col_names.index('comment') %}
  {% for row in results %}
    {% if (row[name_idx] | string) == default_version %}
      {% set comment = row[comment_idx] | string %}
      {% set spec_match = modules.re.search('spec_md5=([0-9a-f]+)', comment) %}
      {% set skill_match = modules.re.search('skill_md5=([0-9a-f]+)', comment) %}
      {{ return({
        'spec_md5': spec_match.group(1) if spec_match else none,
        'skill_md5': skill_match.group(1) if skill_match else ''
      }) }}
    {% endif %}
  {% endfor %}
  {{ return({}) }}
{% endmacro %}

{% macro cortex_agent__skills_hash(agent, projection='canonical') %}
  {# Skill content lives on the stage, not inside the agent spec JSON. Include a
     hash of staged skill files in deploy idempotency so editing SKILL.md mints
     a new agent version even when spec_md5 is unchanged. #}
  {% if projection == 'native_eval' or not execute %}
    {{ return('') }}
  {% endif %}
  {% set entries = [] %}
  {% for skill in agent.get('capabilities', {}).get('skills', []) %}
    {% set source = skill.get('source', {}) %}
    {% if (source.get('type') | string | lower) == 'stage' %}
      {% set rows = run_query("LIST " ~ source.get('path')) %}
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

{% macro cortex_agent__apply_deploy(agent_fqn, spec_json, deploy_alias, mcp_statements=[], skill_hash='') %}
  {% if not execute %}
    {{ return('') }}
  {% endif %}

  {# Fail-closed: this primitive mutates, so guard it directly rather than
     trusting the caller. #}
  {% do cortex_agent__assert_deploy_target('cortex_agent__apply_deploy') %}
  {% if '$$' in spec_json %}
    {{ exceptions.raise_compiler_error("Rendered agent spec contains '$$' delimiter") }}
  {% endif %}

  {% set spec_hash = local_md5(spec_json) %}
  {% set existed = cortex_agent__agent_exists(agent_fqn) %}

  {# Idempotency: skip minting a new version when the rendered spec matches the
     currently deployed DEFAULT version, unless force_agent_recreate is set.
     Skill content hash participates in the skip check because skills live on
     the stage, outside the spec JSON. MCP attach state is still not represented
     (MCP is DDL, not spec), so to (re)attach MCP on an unchanged spec+skill,
     use force_agent_recreate=true. #}
  {% if existed and not var('force_agent_recreate', false) %}
    {% set current_hashes = cortex_agent__current_deploy_hashes(agent_fqn) %}
    {% if current_hashes.get('spec_md5') == spec_hash and current_hashes.get('skill_md5', '') == skill_hash %}
      {% do log("No spec/skill change for " ~ agent_fqn ~ " (spec_md5=" ~ spec_hash ~ ", skill_md5=" ~ skill_hash ~ "); skipping COMMIT. Set var('force_agent_recreate', true) to force a new version.", info=True) %}
      {{ return(agent_fqn) }}
    {% endif %}
  {% endif %}

  {% if not existed %}
    {% do run_query("CREATE AGENT IF NOT EXISTS " ~ agent_fqn ~ " COMMENT = 'Managed by dbt cortex_agent__deploy (sandbox)'") %}
    {% do log("Created agent shell " ~ agent_fqn, info=True) %}
  {% endif %}

  {% set has_draft = cortex_agent__live_draft_exists(agent_fqn) %}
  {% if not has_draft %}
    {% do run_query("ALTER AGENT " ~ agent_fqn ~ " ADD LIVE VERSION FROM LAST") %}
  {% endif %}

  {% do run_query("ALTER AGENT " ~ agent_fqn ~ " MODIFY LIVE VERSION SET SPECIFICATION = $$" ~ spec_json ~ "$$") %}
  {% set commit_result = run_query("ALTER AGENT " ~ agent_fqn ~ " COMMIT") %}
  {# COMMIT returns "Version VERSION$N successfully committed." MODIFY VERSION
     requires the explicit VERSION$N selector; the keyword LAST is NOT valid
     there (verified: raises 001003). Capture the committed version name. #}
  {% set commit_msg = commit_result.rows[0][0] | string if commit_result.rows else '' %}
  {% set version_match = modules.re.search('VERSION\\$\\d+', commit_msg) %}
  {% if not version_match %}
    {{ exceptions.raise_compiler_error("Could not parse committed version from COMMIT result: " ~ commit_msg) }}
  {% endif %}
  {% set new_version = version_match.group(0) %}
  {% do run_query("ALTER AGENT " ~ agent_fqn ~ " MODIFY VERSION " ~ new_version ~ " SET ALIAS = " ~ deploy_alias) %}

  {% set version_comment = target.name ~ ' | inv=' ~ invocation_id ~ ' | spec_md5=' ~ spec_hash ~ ' | skill_md5=' ~ skill_hash %}
  {% do run_query("ALTER AGENT " ~ agent_fqn ~ " MODIFY VERSION " ~ new_version ~ " SET COMMENT = $$" ~ version_comment ~ "$$") %}

  {# Recreate LIVE draft so bare REST /agents/<name>:run resolves after deploy. #}
  {% do run_query("ALTER AGENT " ~ agent_fqn ~ " ADD LIVE VERSION FROM LAST") %}

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
{% macro cortex_agent__build(projection='native_eval', dry_run=true, alias=None) %}
  {# One-command orchestrator: deploy every enabled cortex_agent exposure. Each
     deploy is idempotent and sandbox-guarded, so this is safe to re-run. Pass
     dry_run=false to apply. #}
  {% set deployed = [] %}
  {% for exposure in graph.exposures.values() %}
    {% set ca = exposure.meta.get('cortex_agent', {}) %}
    {% if ca.get('enabled') %}
      {% do cortex_agent__deploy(exposure.name, projection, dry_run, alias) %}
      {% do deployed.append(exposure.name) %}
    {% endif %}
  {% endfor %}
  {% if deployed | length == 0 %}
    {% do log("cortex_agent__build found no enabled cortex_agent exposures", info=True) %}
  {% else %}
    {% do log("cortex_agent__build " ~ ('previewed' if dry_run else 'deployed') ~ " (" ~ projection ~ "): " ~ (deployed | join(', ')), info=True) %}
  {% endif %}
  {{ return(deployed) }}
{% endmacro %}
