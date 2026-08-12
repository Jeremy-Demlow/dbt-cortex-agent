# REQ-017: Tool dependency access contract

## Status

Implemented; consumer live proof pending.

## Summary

Agents with Cortex Search tools must declaratively identify the roles that query each pre-existing Search service. The package validates that metadata and applies the exact object-level grant through the existing guarded Agent grant lifecycle.

## Requirement

1. `cortex_search` tools may declare `access.usage_roles` as a list of role names.
2. `search_service` must be a strict unquoted three-part Snowflake identifier.
3. Every role must be a strict unquoted identifier.
4. The grant lifecycle renders `GRANT USAGE ON CORTEX SEARCH SERVICE <fqn> TO ROLE <role>` for each declaration.
5. Apply remains protected by the package target/database sandbox guard.
6. Tool access metadata is lifecycle metadata and must not enter the Agent specification.

## Out of scope

- Creating or replacing Cortex Search Services.
- Broad schema/future grants.
- Revoking stale grants.
- Access metadata for other tool types; those dependencies are verified by the consumer preflight until a mutation contract is justified.