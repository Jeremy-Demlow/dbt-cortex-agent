# REQ-029: Macro Evaluation Execution Safety

**Status:** In progress; structural macro checks exist, executed macro/installed-consumer proof gaps in `tests/requirement_evidence.json`.

## Summary

Keep the public dbt-native evaluation macro path executable and prevent unsafe
evaluation run names from reaching generated SQL.

## Business Context

The dbt macro path is public. A stale helper can pass source-text tests yet fail
only when an adopter invokes it, while an unchecked run name can cross directly
into generated Snowflake SQL.

## Objective

Make macro dependencies executable contracts and validate SQL-bearing run
identity at the macro boundary.

## User Stories

- As a dbt operator, every documented evaluation macro resolves only shipped helpers.
- As a security reviewer, an unsafe run name cannot reach generated SQL.
- As a maintainer, unreachable legacy branches cannot conceal undefined behavior.

## Dependencies

- Current full-body `cortex_agent` model contract.
- dbt's macro namespace, compiler errors, and `modules.re` support.

## Out of Scope

- Changing Python-native evaluation metrics or lifecycle.
- Restoring legacy exposure-based Agent rendering.

## Acceptance Criteria

1. Every package-qualified Cortex macro call resolves to a macro definition in the installed package.
2. Evaluation run names accept only letters, digits, and underscores before SQL interpolation.
3. Legacy non-model Agent branches and undefined specification helpers are absent from evaluation macros.

## Evidence

`TC-029-01` through `TC-029-03` in `tests/test_cases.md`, implemented by
`tests/test_eval_plan_macros.py` and integration-project dbt parsing.

## Verifier Decision

Complete after recursive macro dependency tests, unsafe-name rejection checks,
the full package suite, and installed-consumer parse pass.

## Notes

The Python-native evaluation path remains unchanged; this requirement repairs
the direct dbt macro interface.