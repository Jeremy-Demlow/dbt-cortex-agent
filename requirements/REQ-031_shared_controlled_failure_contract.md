# REQ-031: Shared Controlled Failure Contract

**Status:** In progress; task 5 locally verified, current connector/inspection and release qualification gaps in `tests/requirement_evidence.json`.

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
4. Evaluation verification reuses the shared controlled-operation predicate, including optional connector errors, instead of maintaining a duplicate list.
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

## Task 5 Hardening Supplement

Status: locally verified (2026-09-17); historical release qualification above does not qualify this slice.

Objective: a later suite or baseline failure never erases completed evaluation
evidence or allows a candidate from another plan to authorize this verification.
Levers: shared error predicate, suite phase tracking, exact loaded-candidate
binding, and in-memory comparison. Data: real candidate/plan fixtures with
synthetic connector failures. Assembly: materialize -> revalidate plan -> execute
-> load once -> bind -> gate -> report prior and current suite evidence.

Acceptance criteria:

1. Connector errors after a successful suite yield structured infrastructure
   failure with earlier results intact; AssertionError/TypeError/AttributeError
   propagate instead of becoming infrastructure failures.
2. Once evaluation returns a candidate path, later load/baseline/gate failure
   retains that path and marks execution completed, not failed. Gate evaluation
   errors are distinct from a completed quality gate that returns failed.
3. The exact loaded candidate's plan identity, signature, model, physical
   resources, ordered refs, metrics, and policies match the current plan before
   intrinsic or baseline gating. Gating consumes that object without reopening
   the candidate file.
4. Offline tests cover these behaviors plus independent evaluation connector
   acquisition/cleanup failures without masking the primary exception.

Dependencies: existing REQ-022 task 2 eligibility rules and REQ-030 task 5 runtime
evidence supplement. Out of scope: tasks 1-4 redesign, baseline policy changes,
new artifact schema versions, live evaluation, and remote state mutation.

Verifier: mandatory offline behavioral tests and critique/fix; no live or full
release qualification claimed. Existing exit codes and top-level outcomes stay
unchanged; suite gate execution errors use `gate=error`, quality rejection keeps
`gate=failed`, and an unattempted gate stays `not_run`.

Task 5 verification (2026-09-17): criteria 1-4 pass in the **446 passed in 7.23s**
offline focused/adjacent run recorded in REQ-030, with warnings treated as errors.
Focused Ruff, configured mypy (12 source files), and `git diff --check` pass.
No new dependency, public CLI option, artifact schema version, baseline tolerance,
or task 1-4 semantic change was introduced. Maker/critic/fix/verifier passes were
sequential in this session; no independent subagent review or live/release proof
is claimed.

Limitations: a cleanup-only failure after `run_evaluation` writes a candidate
leaves the file on disk but raises rather than returning its path. Verify retains
the path once the evaluator returns it; it does not infer a path from directory
scans. Invalid candidate content or identity uses `execution=completed` to mean
the evaluator returned a path, not that its evidence is valid. Gate errors remain
infrastructure failures (exit 2); quality rejection remains exit 1. Existing
`quality_passed` records prior gate outcomes and is not proof that every selected
suite was executed when top-level `passed` is null.