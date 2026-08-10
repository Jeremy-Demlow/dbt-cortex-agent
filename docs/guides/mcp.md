# MCP connectors

Declare a pre-existing external MCP server:

```yaml
capabilities:
  mcp_connectors:
    - name: ticketing
      enabled: true
      server: "{{ target.database }}.AGENTS.TICKETING_MCP_SERVER"
```

MCP is attached with separate `ALTER AGENT ... ADD MCP_SERVER` DDL after Agent
version deployment. It is not part of the specification JSON.

- `mcp_deploy_enabled` defaults to false.
- The package does not provision the external MCP server, OAuth, integrations, or
  network policy.
- MCP may remain attached to the single deployed Agent, but built-in evaluation does not
  invoke it. Built-in Agent Evaluation therefore does not prove MCP behavior; use a
  separate smoke or integration test.
- MCP attachment state is outside the spec/skill hash and may require an intentional
  forced deployment when reattachment is needed.
