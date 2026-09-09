# REQ-031: Shared Controlled Failure Contract

**Status:** Complete (`0.0.8`)

## Summary

Use one narrow controlled-operation error contract across deployment, routing,
and evaluation while preserving programming-defect visibility.

## Business Context

Lifecycle operations need stable, structured failure evidence for expected I/O,
validation, runtime, and Snowflake connector failures. Duplicated exception
tuples can drift and cause the same failure to be classified differently across
commands.

## Objective

Centralize expected operational failure classification without broadening it to
programming defects, and remove repeated durable-state inspection logic without
changing lifecycle behavior.

## User Stories

- As an operator, equivalent operational failures receive equivalent structured outcomes.
- As a developer, assertion and programming defects continue to propagate with tracebacks.
- As a maintainer, routing reconciliation uses one tested state-inspection helper.

## Dependencies

- REQ-021 Python design and maintainability.
- REQ-030 runtime failure evidence.

## Out of Scope

- Adding new exception classes to the controlled standard-library set.
- Changing Agent DDL, routing order, CLI output, or exit codes.
- Suppressing unexpected failures during post-error state inspection.

## Acceptance Criteria

1. Expected `OSError`, `RuntimeError`, and `ValueError` instances use the shared controlled-operation classification.
2. Snowflake connector exception classes use the same controlled-operation classification without importing the optional connector in the base package.
3. Programming defects such as `AssertionError` are not classified as controlled operation failures.
4. Evaluation verification reuses the shared controlled-operation exception tuple instead of maintaining a duplicate list.
5. Repeated routing failure-state inspection is factored into one helper that re-raises programming defects and returns controlled inspection errors as evidence.

## Evidence

`TC-031-01` through `TC-031-05` in `tests/test_cases.md`, implemented by
`tests/test_domain.py`, `tests/test_eval_verify.py`, and `tests/test_lifecycle.py`.

## Verifier Decision

Complete when focused tests, the full package suite, Ruff, mypy, mutation tests,
distribution verification, and installed-consumer checks pass for `0.0.8`.

## Notes

The shared tuple remains suitable for direct `except` clauses. Connector errors
are recognized by the predicate because the Snowflake connector is an optional
runtime dependency.