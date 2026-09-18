# Snowflake setup and security

Use separate deploy, runtime, and evaluation responsibilities in an isolated
sandbox first. Exact grant syntax may vary with Snowflake feature availability
and account policy; validate least privilege with the account security owner.

| Responsibility | Required access | Not granted by this package |
|---|---|---|
| dbt parse/render | local profile for parse; compile can open the adapter and require live credentials | Agent DDL, stage writes, evaluation spend |
| Agent deploy role | database/schema usage; warehouse usage; create/alter Agent privileges; referenced semantic view/search/procedure access | consumer runtime access; broad role inheritance |
| Skill uploader | stage/database/schema access and Snow CLI authentication; explicit target/database allowlists | Agent deployment or Agent usage |
| Runtime consumer | database/schema and warehouse usage; `USAGE ON AGENT`; privileges needed by referenced resources | automatic semantic-view, search-service, procedure, or stage grants |
| Evaluation operator | deployed Agent usage and monitor; eval table access/create for verify; pre-existing evaluation-stage write/read; warehouse usage; Agent Evaluation privileges | Agent deployment, shared-stage provisioning, privilege grants |
| MCP deployer | access to the pre-existing external MCP server and Agent attachment privileges | MCP server creation or credential management |

The package has no public grant macro. Historical `access.usage_roles` and
`access.monitor_roles` metadata does not apply grants. Provision Agent `USAGE`
and `MONITOR` and dependency privileges through adopter-owned access management;
see [access control](../guides/access-control.md). `eval verify --apply` builds
and tests the selected eval table; `eval run --apply` requires it already built.
Neither path provisions the shared evaluation stage or deploys the Agent.

## Required execution context

Provide target, connection, database, schema, warehouse, and authentication
through approved local dbt/Snowflake configuration. Do not store credentials in
Agent/eval YAML, dbt vars, examples, or artifacts.

For an applied CLI operation:

- pass `--connection` explicitly (an environment-only connection is rejected),
- resolve an approved connection/default database; authorize every selected
  manifest resource database independently, including cross-database dependencies,
- pass both CLI allowlists,
- configure matching dbt target/database allowlists,
- use a role scoped to the operation rather than one all-purpose owner role.

The materialization uses the invoking dbt role; `meta.agent_role` does not switch
it. The CLI execution context (including `--role`) must agree with the intended
dbt profile. Resolve schema names from the manifest: default dbt schema generation
combines the target schema and a custom schema rather than using the custom
schema alone. Do not copy a destructive confirmation FQN from another project.

Begin with [doctor and non-mutating quickstart](quickstart.md), then review the
[lifecycle](../guides/lifecycle.md) or [evaluation](../guides/evaluations.md)
boundary before granting mutation or spend.