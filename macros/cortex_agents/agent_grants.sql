{% macro cortex_agent__grant_usage(agent_name, projection='canonical', dry_run=True) %}
  {# Render (and, on the sandbox-guarded apply path, execute) USAGE grants for a
     deployed Cortex Agent. Access is declared in meta.cortex_agent.access.usage_roles
     (a flat list of role names). Grants are DDL, not part of the agent spec, so this
     is a separate path from cortex_agent__deploy and does not affect spec rendering
     or the goldens (same treatment as MCP ADD MCP_SERVER).

     dry_run (default true): log the GRANT statements only. dry_run=false: enforce the
     sandbox guard and execute each grant. Returns the list of rendered statements. #}
  {% set exposure = cortex_agent__get_agent(agent_name) %}
  {% set agent = exposure.meta.get('cortex_agent', {}) %}
  {% set agent_fqn = cortex_agent__target_agent_fqn(agent, projection) %}
  {% set usage_roles = agent.get('access', {}).get('usage_roles', []) %}

  {% set statements = [] %}
  {% for role in usage_roles %}
    {% if role %}
      {% do statements.append("GRANT USAGE ON AGENT " ~ agent_fqn ~ " TO ROLE " ~ role) %}
    {% endif %}
  {% endfor %}

  {% if statements | length == 0 %}
    {% do log("[cortex_agent__grant_usage] no access.usage_roles declared for " ~ agent_name ~ " -- nothing to grant", info=True) %}
    {{ return([]) }}
  {% endif %}

  {% if dry_run %}
    {% do log("[DRY RUN] would grant USAGE on " ~ agent_fqn ~ " to " ~ (usage_roles | length) ~ " role(s):", info=True) %}
    {% for stmt in statements %}
      {% do log("[DRY RUN] " ~ stmt, info=True) %}
    {% endfor %}
    {{ return(statements) }}
  {% else %}
    {% do cortex_agent__assert_deploy_target('cortex_agent__grant_usage') %}
    {% for stmt in statements %}
      {% do run_query(stmt) %}
      {% do log("[cortex_agent__grant_usage] applied: " ~ stmt, info=True) %}
    {% endfor %}
    {{ return(statements) }}
  {% endif %}
{% endmacro %}
