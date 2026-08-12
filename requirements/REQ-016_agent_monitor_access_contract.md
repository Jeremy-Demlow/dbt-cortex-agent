# REQ-016: Agent monitor access contract

## Summary

Extend the existing Agent-object grant lifecycle so evaluation roles can receive
the `USAGE` and `MONITOR` privileges required by Snowflake Agent Evaluations.

## Business context

Evaluation execution is asynchronous. A role can create datasets and tasks yet
still fail ingestion if it cannot use and monitor the evaluated Agent. This must
be declarative, reviewable metadata rather than an out-of-band account fix.

## Requirement

The package grant lifecycle must support the complete Agent-object privileges
needed by runtime and evaluation roles without embedding grants in rendered Agent
specifications.

## Acceptance criteria

- `access.usage_roles` renders `GRANT USAGE ON AGENT` statements.
- `access.monitor_roles` renders `GRANT MONITOR ON AGENT` statements.
- The existing `agent grant` CLI applies both statement types through the
  sandbox-guarded `cortex_agent__grant_usage` macro.
- Starter metadata demonstrates separate runtime and evaluation role inputs.
- Database, schema, warehouse, tool, task, Cortex, and stage privileges remain
  consumer responsibilities.

## Dependencies

- REQ-004 lifecycle safety and sandbox mutation guards.
- REQ-013 single physical Agent evaluation.
- Snowflake Agent Evaluation access-control requirements.

## Out of scope

- Creating roles or granting database, schema, warehouse, task, AI function,
  semantic-view, Cortex Search, procedure, stage, skill, or MCP privileges.
- Automatically inferring which roles are evaluation operators.

## Notes

An evaluation role normally appears in both `usage_roles` and `monitor_roles`.
Separate lists preserve least privilege for runtime roles that do not inspect
Agent observability.