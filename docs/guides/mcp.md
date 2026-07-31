# MCP connectors

Declare a pre-existing external MCP server:

```yaml
capabilities:
  mcp_connectors:
    - name: ticketing
      enabled: true
      server: "{{ target.database }}.AGENTS.TICKETING_MCP_SERVER"
      evaluation_supported: false
```

MCP is attached with separate `ALTER AGENT ... ADD MCP_SERVER` DDL after Agent
version deployment. It is not part of the specification JSON.

- `mcp_deploy_enabled` defaults to false.
- The package does not provision the external MCP server, OAuth, integrations, or
  network policy.
- Native eval does not attach MCP.
- Built-in Agent Evaluation does not prove MCP behavior; use a separate smoke test.
- MCP attachment state is outside the spec/skill hash and may require an intentional
  forced deployment when reattachment is needed.
