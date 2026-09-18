# Access control

Grants are adopter-owned infrastructure. This package does not ship a public
grant macro or an Agent grant CLI command. Historical `access.usage_roles` and
`access.monitor_roles` declarations are not an implemented grant contract;
adding them does not grant access during deployment. No grant feature is added
by this documentation correction.

Have the account security owner provision and verify the operation-specific
privileges on the manifest-resolved objects before applying commands:

- Runtime callers need `USAGE ON AGENT` plus appropriate database/schema,
  warehouse, and referenced-resource privileges.
- Evaluation operators normally need Agent `USAGE` and `MONITOR` (or ownership),
  eval-table access, a pre-existing evaluation stage, warehouse access, and the
  account's Agent Evaluation privileges.
- Deployment uses the approved invoking dbt role. The materialization does not
  switch roles or grant role inheritance.

Database/schema, warehouse, semantic-view, search-service, procedure, stage, MCP,
and Cortex privileges remain consumer responsibilities. Metadata is not proof of
effective RBAC. See [Snowflake setup](../getting-started/snowflake-setup.md).
