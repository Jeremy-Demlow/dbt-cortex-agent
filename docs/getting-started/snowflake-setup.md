# Snowflake setup and security

Use separate deploy, runtime, and evaluation responsibilities in an isolated
sandbox first. Exact grant syntax may vary with Snowflake feature availability
and account policy; validate least privilege with the account security owner.

| Responsibility | Required access | Not granted by this package |
|---|---|---|
| dbt parse/render | profile access to resolve the target; metadata dependencies | Agent DDL, stage writes, evaluation spend |
| Agent deploy role | database/schema usage; warehouse usage; create/alter Agent privileges; referenced semantic view/search/procedure access | consumer runtime access; broad role inheritance |
| Skill uploader | stage/database/schema access and Snow CLI authentication; explicit target/database allowlists | Agent deployment or Agent usage |
| Runtime consumer | database/schema and warehouse usage; `USAGE ON AGENT`; privileges needed by referenced resources | automatic semantic-view, search-service, procedure, or stage grants |
| Evaluation operator | deployed native-eval Agent usage; materialized eval table access; evaluation-stage create/write/read; warehouse usage; Agent Evaluation privileges | creation of the Agent/table prerequisites by the CLI |
| MCP deployer | access to the pre-existing external MCP server and Agent attachment privileges | MCP server creation or credential management |

`access.usage_roles` plus `cortex_agent__grant_usage` grants only `USAGE ON AGENT`.
It does not grant database/schema, warehouse, semantic view, Cortex Search,
procedure, stage, MCP, or Agent Evaluation privileges.

## Required execution context

Provide target, connection, database, schema, warehouse, and authentication
through approved local dbt/Snowflake configuration. Do not store credentials in
Agent/eval YAML, dbt vars, examples, or artifacts.

For an applied CLI operation:

- pass `--connection` explicitly (an environment-only connection is rejected),
- pass/resolve a database that matches dbt's manifest target,
- pass both CLI allowlists,
- configure matching dbt target/database allowlists,
- use a role scoped to the operation rather than one all-purpose owner role.

Begin with [doctor and non-mutating quickstart](quickstart.md), then review the
[lifecycle](../guides/lifecycle.md) or [evaluation](../guides/evaluations.md)
boundary before granting mutation or spend.