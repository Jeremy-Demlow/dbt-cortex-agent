# REQ-023: dbt Macro API, Safety, and Reconciliation

**Status:** Complete (`0.0.6`)

## Summary

Replace the interleaved macro implementation with one minimal public API and a restartable reconciliation process that treats Agent DDL as non-transactional.

## Acceptance Criteria

1. A documented minimal public macro surface is invoked successfully from an installed consumer project.
2. Identifier, policy, Agent contract, state inspection, reconciliation, version routing, evaluation planning, runtime, and gating concerns are separated into focused macros.
3. SQL-bearing values are validated or safely serialized at their boundary; raw user strings are not concatenated into executable SQL.
4. The materialization does not switch session roles; the approved invoking connection role is authoritative.
5. Pre/post hooks and `adapter.commit()` are not described or relied on as rollback for Agent DDL.
6. Reconciliation inspects current Agent, committed versions, aliases, DEFAULT, LAST, LIVE, and managed content metadata before mutation.
7. Changed content commits exactly one immutable version; unchanged content commits none, even when DEFAULT intentionally points to an older version.
8. A failure after a durable phase emits enough state for a retry to resume without another content version.
9. Alias/default, profile/comment, MCP, grants, and LIVE reconciliation are independently retryable and verified after application.
10. Evaluation plans bind exact result identity, stable refs, target context, policy, and pre-START Agent version provenance.
11. Native evaluation never replaces an existing result table or silently collides normalized run identities.
12. All orphaned `cortex_agent__legacy_*` macros and fictional public API documentation are removed after active behavior characterization passes.

## Evidence

Offline qualification on 2026-08-28 includes dbt 1.10/1.11 installed-wheel
verification, materialization contract tests, and structured reconciliation
phase parsing from successful and failed dbt output. Live lifecycle replay is
completed with the same exact wheel.

`TC-023-01` through `TC-023-12` in `tests/test_cases.md`.