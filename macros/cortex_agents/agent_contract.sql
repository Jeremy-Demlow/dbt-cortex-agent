{% macro cortex_agent__get_agent(agent_name) %}
  {% set matches = [] %}
  {% for node in graph.nodes.values() %}
    {% if node.resource_type == 'model' and node.config.get('materialized') == 'cortex_agent' and node.name == agent_name %}
      {% set cortex_agent = node.config.get('meta', {}).get('cortex_agent', {}) %}
      {% if cortex_agent.get('enabled', true) %}
        {% do matches.append(node) %}
      {% endif %}
    {% endif %}
  {% endfor %}
  {% for exposure in graph.exposures.values() %}
    {% set cortex_agent = exposure.meta.get('cortex_agent', {}) %}
    {% if cortex_agent.get('enabled') and exposure.name == agent_name %}
      {% do matches.append(exposure) %}
    {% endif %}
  {% endfor %}

  {% if matches | length == 0 %}
    {{ exceptions.raise_compiler_error("No enabled cortex_agent model or exposure found for '" ~ agent_name ~ "'") }}
  {% endif %}
  {% if matches | length > 1 %}
    {{ exceptions.raise_compiler_error("Multiple enabled cortex_agent models/exposures found for '" ~ agent_name ~ "'") }}
  {% endif %}

  {{ return(matches[0]) }}
{% endmacro %}

{% macro cortex_agent__agent_meta(resource) %}
  {% if resource.resource_type == 'model' %}
    {{ return(resource.config.get('meta', {}).get('cortex_agent', {})) }}
  {% endif %}
  {{ return(resource.meta.get('cortex_agent', {})) }}
{% endmacro %}

{% macro cortex_agent__is_model(resource) %}
  {{ return(resource.resource_type == 'model' and resource.config.get('materialized') == 'cortex_agent') }}
{% endmacro %}

{% macro cortex_agent__get_model_node(model_name) %}
  {% set matches = [] %}
  {% for node in graph.nodes.values() %}
    {% if node.resource_type == 'model' and node.name == model_name %}
      {% do matches.append(node) %}
    {% endif %}
  {% endfor %}

  {% if matches | length == 0 %}
    {{ exceptions.raise_compiler_error("semantic_view_model '" ~ model_name ~ "' does not resolve to a dbt model") }}
  {% endif %}
  {% if matches | length > 1 %}
    {{ exceptions.raise_compiler_error("semantic_view_model '" ~ model_name ~ "' resolves to multiple dbt models") }}
  {% endif %}

  {{ return(matches[0]) }}
{% endmacro %}

{% macro cortex_agent__semantic_view_fqn(model_name) %}
  {% set node = cortex_agent__get_model_node(model_name) %}
  {% set materialized = node.config.get('materialized') %}

  {% if materialized != 'semantic_view' %}
    {{ exceptions.raise_compiler_error("semantic_view_model '" ~ model_name ~ "' must be materialized as semantic_view, got '" ~ materialized ~ "'") }}
  {% endif %}

  {% set database_name = (node.database or target.database) | upper %}
  {% set schema_name = node.schema | upper %}
  {% set identifier = (node.alias or node.name) | upper %}
  {{ return(database_name ~ '.' ~ schema_name ~ '.' ~ identifier) }}
{% endmacro %}

{% macro cortex_agent__validate(agent_name) %}
  {% set resource = cortex_agent__get_agent(agent_name) %}
  {% set agent = cortex_agent__agent_meta(resource) %}
  {% if cortex_agent__is_model(resource) %}
    {{ exceptions.raise_compiler_error("cortex_agent model '" ~ agent_name ~ "' is deployed by dbt build, not cortex_agent__render_spec or cortex_agent__deploy") }}
  {% endif %}
  {% set tools = agent.get('tools', []) %}

  {% if not agent.get('snowflake_name') %}
    {{ exceptions.raise_compiler_error("Agent '" ~ agent_name ~ "' missing meta.cortex_agent.snowflake_name") }}
  {% endif %}
  {% if not (agent.get('model', {}).get('orchestration') | default('', true) | trim) %}
    {{ exceptions.raise_compiler_error("Agent '" ~ agent_name ~ "' must explicitly define model.orchestration") }}
  {% endif %}
  {% if tools | length == 0 %}
    {{ exceptions.raise_compiler_error("Agent '" ~ agent_name ~ "' must define at least one tool") }}
  {% endif %}

  {% for tool in tools %}
    {% if not tool.get('name') %}
      {{ exceptions.raise_compiler_error("Agent '" ~ agent_name ~ "' has a tool missing name") }}
    {% endif %}
    {% if not tool.get('type') %}
      {{ exceptions.raise_compiler_error("Tool '" ~ tool.get('name', '<unnamed>') ~ "' missing type") }}
    {% endif %}
    {% if tool.get('type') == 'cortex_analyst_text_to_sql' %}
      {% if not tool.get('semantic_view_model') %}
        {{ exceptions.raise_compiler_error("Tool '" ~ tool.get('name') ~ "' missing semantic_view_model") }}
      {% endif %}
      {% do cortex_agent__semantic_view_fqn(tool.get('semantic_view_model')) %}
    {% elif tool.get('type') == 'cortex_search' %}
      {% if not tool.get('search_service') %}
        {{ exceptions.raise_compiler_error("Tool '" ~ tool.get('name') ~ "' missing search_service") }}
      {% endif %}
      {% do cortex_agent__unquoted_fqn(tool.get('search_service'), "Tool '" ~ tool.get('name') ~ "' search_service") %}
      {% set usage_roles = tool.get('access', {}).get('usage_roles', []) %}
      {% if usage_roles is string or usage_roles is mapping %}
        {{ exceptions.raise_compiler_error("Tool '" ~ tool.get('name') ~ "' access.usage_roles must be a list") }}
      {% endif %}
      {% for role in usage_roles %}
        {% do cortex_agent__unquoted_identifier(role, "Tool '" ~ tool.get('name') ~ "' usage role") %}
      {% endfor %}
    {% elif tool.get('type') == 'generic' %}
      {% if not tool.get('identifier') %}
        {{ exceptions.raise_compiler_error("Tool '" ~ tool.get('name') ~ "' missing identifier") }}
      {% endif %}
    {% else %}
      {{ exceptions.raise_compiler_error("Tool '" ~ tool.get('name') ~ "' type '" ~ tool.get('type') ~ "' is not implemented by cortex_agent__build_spec") }}
    {% endif %}
  {% endfor %}

  {% set skills = agent.get('capabilities', {}).get('skills', []) %}
  {% for skill in skills %}
    {% if not skill.get('name') %}
      {{ exceptions.raise_compiler_error("Agent '" ~ agent_name ~ "' has a skill missing name") }}
    {% endif %}
    {% set source = skill.get('source', {}) %}
    {% if not source.get('type') or not source.get('path') %}
      {{ exceptions.raise_compiler_error("Skill '" ~ skill.get('name') ~ "' must declare source.type and source.path") }}
    {% endif %}
    {% if execute and var('cortex_agent_validate_staged_skills', false) and (source.get('type') | string | lower) == 'stage' %}
      {% set ls_result = run_query("LIST " ~ source.get('path') ~ " PATTERN='.*SKILL[.]md'") %}
      {% if ls_result.rows | length == 0 %}
        {{ exceptions.raise_compiler_error("Skill '" ~ skill.get('name') ~ "' source path has no SKILL.md: " ~ source.get('path')) }}
      {% endif %}
    {% endif %}
  {% endfor %}

  {% set mcp_connectors = agent.get('capabilities', {}).get('mcp_connectors', []) %}
  {% for connector in mcp_connectors %}
    {% if connector.get('enabled') and not connector.get('server') %}
      {{ exceptions.raise_compiler_error("MCP connector '" ~ connector.get('name', '<unnamed>') ~ "' is enabled but missing 'server' (the EXTERNAL MCP SERVER FQN) required to attach it via ALTER AGENT ... ADD MCP_SERVER") }}
    {% endif %}
  {% endfor %}

  {% do log("Validated cortex agent exposure: " ~ agent_name ~ " (full specification)", info=True) %}
  {{ return(True) }}
{% endmacro %}
