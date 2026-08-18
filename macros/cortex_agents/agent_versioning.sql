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
