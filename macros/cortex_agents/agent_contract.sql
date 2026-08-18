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
  {% if matches | length == 0 %}
    {{ exceptions.raise_compiler_error("No enabled cortex_agent model found for '" ~ agent_name ~ "'") }}
  {% endif %}
  {% if matches | length > 1 %}
    {{ exceptions.raise_compiler_error("Multiple enabled cortex_agent models found for '" ~ agent_name ~ "'") }}
  {% endif %}

  {{ return(matches[0]) }}
{% endmacro %}

{% macro cortex_agent__agent_meta(resource) %}
  {{ return(resource.config.get('meta', {}).get('cortex_agent', {})) }}
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
