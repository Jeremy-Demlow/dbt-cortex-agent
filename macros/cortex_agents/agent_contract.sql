{% macro cortex_agent__get_agent(agent_name) %}
  {% set matches = [] %}
  {% for exposure in graph.exposures.values() %}
    {% set cortex_agent = exposure.meta.get('cortex_agent', {}) %}
    {% if cortex_agent.get('enabled') and exposure.name == agent_name %}
      {% do matches.append(exposure) %}
    {% endif %}
  {% endfor %}

  {% if matches | length == 0 %}
    {{ exceptions.raise_compiler_error("No enabled cortex_agent exposure found for '" ~ agent_name ~ "'") }}
  {% endif %}
  {% if matches | length > 1 %}
    {{ exceptions.raise_compiler_error("Multiple enabled cortex_agent exposures found for '" ~ agent_name ~ "'") }}
  {% endif %}

  {{ return(matches[0]) }}
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

{% macro cortex_agent__validate_projection(projection) %}
  {% if projection not in ['canonical', 'native_eval'] %}
    {{ exceptions.raise_compiler_error("projection must be 'canonical' or 'native_eval', got '" ~ projection ~ "'") }}
  {% endif %}
  {{ return(projection) }}
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

{% macro cortex_agent__validate(agent_name, projection='canonical') %}
  {% do cortex_agent__validate_projection(projection) %}
  {% set exposure = cortex_agent__get_agent(agent_name) %}
  {% set agent = exposure.meta.get('cortex_agent', {}) %}
  {% set tools = agent.get('tools', []) %}

  {% if not agent.get('snowflake_name') %}
    {{ exceptions.raise_compiler_error("Agent '" ~ agent_name ~ "' missing meta.cortex_agent.snowflake_name") }}
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
    {% elif tool.get('type') == 'generic' %}
      {% if not tool.get('identifier') %}
        {{ exceptions.raise_compiler_error("Tool '" ~ tool.get('name') ~ "' missing identifier") }}
      {% endif %}
    {% else %}
      {{ exceptions.raise_compiler_error("Tool '" ~ tool.get('name') ~ "' type '" ~ tool.get('type') ~ "' is not implemented by cortex_agent__build_spec") }}
    {% endif %}
  {% endfor %}

  {% set skills = agent.get('capabilities', {}).get('skills', []) %}
  {% if projection == 'canonical' %}
    {% for skill in skills %}
      {% if not skill.get('name') %}
        {{ exceptions.raise_compiler_error("Agent '" ~ agent_name ~ "' has a skill missing name") }}
      {% endif %}
      {% set source = skill.get('source', {}) %}
      {% if not source.get('type') or not source.get('path') %}
        {{ exceptions.raise_compiler_error("Skill '" ~ skill.get('name') ~ "' must declare source.type and source.path for the canonical render") }}
      {% endif %}
      {% if execute and var('cortex_agent_validate_staged_skills', false) and (source.get('type') | string | lower) == 'stage' %}
        {% set ls_result = run_query("LIST " ~ source.get('path') ~ " PATTERN='.*SKILL[.]md'") %}
        {% if ls_result.rows | length == 0 %}
          {{ exceptions.raise_compiler_error("Skill '" ~ skill.get('name') ~ "' source path has no SKILL.md: " ~ source.get('path')) }}
        {% endif %}
      {% endif %}
    {% endfor %}
  {% endif %}

  {% set mcp_connectors = agent.get('capabilities', {}).get('mcp_connectors', []) %}
  {% if projection == 'canonical' %}
    {% for connector in mcp_connectors %}
      {% if connector.get('enabled') and not connector.get('server') %}
        {{ exceptions.raise_compiler_error("MCP connector '" ~ connector.get('name', '<unnamed>') ~ "' is enabled but missing 'server' (the EXTERNAL MCP SERVER FQN) required to attach it via ALTER AGENT ... ADD MCP_SERVER") }}
      {% endif %}
    {% endfor %}
  {% endif %}
  {% if projection == 'native_eval' and mcp_connectors | selectattr('enabled') | list | length > 0 %}
    {% do log("[INFO] Native-eval projection: MCP connectors are declared in canonical metadata but are not attached for built-in EXECUTE_AI_EVALUATION.", info=True) %}
  {% endif %}

  {% set render_label = 'native-eval projection' if projection == 'native_eval' else 'canonical render' %}
  {% do log("Validated cortex agent exposure: " ~ agent_name ~ " (" ~ render_label ~ ")", info=True) %}
  {{ return(True) }}
{% endmacro %}
