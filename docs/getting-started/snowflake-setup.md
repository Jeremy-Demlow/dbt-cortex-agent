# Snowflake setup

Use separate responsibilities for deployment and runtime consumption.

## Deploy role

The role running mutating package macros needs, at minimum:

- `USAGE` on the target database and schemas.
- `USAGE` on the query warehouse.
- privileges required to create and alter Agents in the Agent schema.
- access to semantic views, search services, and procedures referenced by tools.
- stage creation/write privileges when using package-native evaluation or staged skills.
- Cortex Agent Evaluation privileges when starting native evaluations.
- optional permission to attach a pre-existing external MCP server.

Exact privileges can vary by Snowflake feature release and account policy. Validate
the setup in an isolated sandbox before using a mutating macro.

## Runtime role

`access.usage_roles` and `cortex_agent__grant_usage` grant only:

```sql
GRANT USAGE ON AGENT <agent_fqn> TO ROLE <role>;
```

They do not grant database/schema, warehouse, semantic-view, search-service,
procedure, stage, or Cortex database-role privileges. Manage those separately.

## Required dbt profile context

Provide account, user/authentication, role, warehouse, database, and target name
explicitly. Mutations are allowed only when `target.name` equals
`cortex_agent_deploy_target`.

Start with render and dry-run operations before any live mutation.
