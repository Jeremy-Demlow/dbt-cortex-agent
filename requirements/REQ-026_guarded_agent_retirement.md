# REQ-026: Guarded Agent Retirement

**Status:** Complete (`0.0.6`)

## Summary

Support deliberate Agent deletion as an explicit lifecycle action without coupling destructive behavior to dbt graph removal.

## Acceptance Criteria

1. `agent drop --agent <logical-name>` is preview-first and resolves exactly one manifest-owned physical Agent.
2. Apply requires `--apply`, an explicit connection, complete target/database allowlists, and `--confirm-agent` equal to the exact physical FQN.
3. Offline preview identifies the physical Agent and retained dependent asset classes; apply inventories versions, aliases, DEFAULT, and LIVE before deletion.
4. Python emits no Agent DDL; a validated dbt macro owns `DROP AGENT IF EXISTS`.
5. Apply re-inspects and verifies that the Agent is absent before reporting success.
6. Dropping a nonexistent Agent is an idempotent success whose output distinguishes already absent from newly dropped.
7. Removing or disabling a dbt model never implicitly drops its physical Agent.
8. Drop does not remove dbt source files, Semantic Views, Cortex Sense contexts, Search services, stages/skills, MCP servers, evaluation results, candidates, or baselines.
9. Controlled failures and partial state use stable JSON and exit semantics without a traceback or false cleanup claim.
10. Protected zero-state proof uses the guarded public path for bounded cleanup and asserts retained dependencies remain.

## Evidence

Offline qualification on 2026-08-28 verifies preview-only defaults, exact-FQN
confirmation, allowlists, newly-dropped versus already-absent output, and no
implicit retirement on model removal. Protected cleanup removed both dedicated
proof Agents and post-cleanup `SHOW AGENTS` returned no rows.

`TC-026-01` through `TC-026-10` in `tests/test_cases.md`.