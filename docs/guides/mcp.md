# MCP connectors

The current full-body `cortex_agent` materialization does not provision or
attach MCP servers. Treat MCP as separately managed Agent infrastructure until
a package-owned, executable attachment path is released.

An adopter may retain intended MCP configuration in reviewed project metadata
or native specification fields supported by its Snowflake environment, for
example:

```yaml
capabilities:
  mcp_connectors:
    - name: ticketing
      enabled: true
      server: "{{ target.database }}.AGENTS.TICKETING_MCP_SERVER"
```

Do not assume that `agent deploy` applies this mapping. Release `0.0.8` passes no
MCP attachment statements into the active materialization. Any manual attachment
must use a separately reviewed Snowflake operation and independent evidence.

- The package does not provision the external MCP server, OAuth, integrations, or
  network policy.
- Built-in Agent Evaluation does not prove MCP behavior; use a separate runtime
  or integration test.
- MCP state is outside the managed specification and skill content identity, so
  inspect it independently before and after an Agent release.
- Do not place credentials or OAuth secrets in dbt metadata, Agent models, or
  retained artifacts.
