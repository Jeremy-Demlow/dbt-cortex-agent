# REQ-022: Package-Native Workflow Safety and Proof

**Status:** Complete (`0.0.6`)

## Summary

Harden `agent deploy` and `eval verify` so reusable execution lives in the package, all policy is checked before effects, and partial durable work is reported honestly.

## Acceptance Criteria

1. Deploy authorizes the selected target and every Agent, stage, and dependency database before upload or dbt execution.
2. Preview resolves plans without credentials, remote calls, local evidence writes, mutation, runtime invocation, or paid evaluation.
3. Apply uses one explicit connection context consistently across dbt, Snow CLI, connector, role, database, schema, and warehouse operations.
4. Authentication modes are either proven end to end for both package and dbt clients or rejected before execution with an actionable diagnostic.
5. Deploy reports each durable phase, including successful uploads or version commits preceding a later failure.
6. Evaluation completes all resource and policy validation before eval-model build or paid work.
7. Numeric thresholds, tolerances, scores, counts, and retry settings reject NaN, infinity, malformed values, and incomplete cardinality.
8. Evaluation infrastructure is pre-provisioned or explicitly managed outside the paid run; evaluation does not opportunistically create shared stages.
9. Multi-suite verification preserves every completed suite result and reports aggregate quality separately from infrastructure failure.
10. Candidate and diagnostic identities are collision-safe, contained, and never overwrite prior evidence implicitly.
11. Protected exact-wheel proof exercises the same public deploy and verify commands customers use.
12. Adopter scripts retain only fleet selection, environment policy, approvals, and reporting; they do not duplicate package mechanics.

## Partial-State Contract

Snowflake Agent DDL and uploads are durable phase by phase. Output records what completed and what failed; it never claims transaction rollback.

## Evidence

Offline qualification on 2026-08-28 covers policy-before-effect behavior,
authentication rejection, durable dbt phase markers, partial failures, numeric
validation, multi-suite evidence, and artifact collision safety. The protected
exact-wheel proof completed with wheel SHA256
`f926445177e3c2a93a7cc7089e909a7c6c310d9761a9650e5a1cf3fedcfbe4eb`.

`TC-022-01` through `TC-022-12` in `tests/test_cases.md`.