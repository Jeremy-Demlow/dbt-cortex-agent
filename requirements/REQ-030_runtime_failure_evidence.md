# REQ-030: Runtime Failure Evidence

**Status:** Complete (`0.0.7`)

## Summary

Preserve useful runtime evidence on assertion failure and distinguish expected
operational failures from programming defects.

## Business Context

Runtime calls and partial Agent DDL can incur spend or durable state before a
later assertion fails. Operators need the evidence that already exists, while
developers need unexpected code defects to remain visible.

## Objective

Fail before avoidable runtime spend, retain normalized assertion evidence, and
keep operational and programming failure classes distinct.

## User Stories

- As an operator, a failed expected-tool assertion retains the response that explains it.
- As a cost owner, a known evidence collision fails before another Agent invocation.
- As a developer, programming defects remain visible.
- As a multi-database operator, resource authorization is independent of connection defaults.

## Dependencies

- Normalized Agent SSE result contract.
- Preview-first operations and repeatable database allowlists.

## Out of Scope

- Changing the established exit `2` for runtime assertion failure.
- Requiring every manifest resource to use the connection-default database.

## Acceptance Criteria

1. An expected-tool mismatch emits the normalized Agent response with `passed=false` and preserves exit `2`.
2. An existing raw-event destination is rejected before Agent invocation.
3. Unexpected programming exceptions are not converted into controlled partial-operation outcomes.
4. Multi-database deployment authorizes every manifest-resolved resource database independently of connection-default database context.

## Evidence

`TC-030-01` through `TC-030-04` in `tests/test_cases.md`, implemented by
`tests/test_agent_commands.py`, `tests/test_lifecycle.py`, and
`tests/test_deployment.py`.

## Verifier Decision

Complete after command, routing, deployment, multi-database, and full regression
tests pass with the `0.0.7` wheel.

## Notes

Expected-tool assertion failure intentionally retains exit `2` for compatibility
with the established runtime command contract.