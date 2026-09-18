# REQ-030: Runtime Failure Evidence

**Status:** Locally verified; task 5 offline evidence retained. Current exact-wheel/full-release qualification is pending, not implied by historical `0.0.7` status.

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

## Task 5 Hardening Supplement

Status: locally verified (2026-09-17); historical release qualification above does not qualify this slice.

Objective: operators can diagnose interrupted runtime work from already-observed
evidence, without losing the primary failure or accidentally reporting success.
Levers: incremental framing/normalization, bounded retention, connector timeout
arguments, monotonic deadline checks, and independent resource cleanup. Data:
existing synthetic SSE fixtures and injected connector/HTTP failures. Assembly:
validate -> acquire -> consume bounded events -> retain evidence -> close -> report.

Acceptance criteria:

1. Controlled stream, malformed-stream, byte/event-limit, and deadline errors
   preserve bounded prior raw events and normalized evidence; explicit raw paths
   remain collision-safe. Programming defects propagate unchanged.
2. The invocation budget begins before connector setup and uses a monotonic
   clock. Connector setup/query and HTTP open receive timeout budgets, and reads
   check remaining time before and after blocking. No hard wall-clock guarantee
   is claimed for APIs, retries, DNS, or cleanup that cannot enforce cancellation.
3. Every acquired response/cursor/connection is independently closed even when
   acquisition of the next resource or another close fails. Cleanup errors do
   not mask primary failures; cleanup-only failures cannot report success.
4. Agent smoke reports partial normalized evidence and exits 2 on runtime failure.

Scope: task 5 only; preserve tasks 1-4. No network, dependency install, live
Snowflake, baseline movement, commits, or branches. No new framework, async
client, process isolation, or claim of remote cancellation. Existing domain
classification and focused resource/error helpers are the implementation pattern.

Verifier: mandatory offline behavioral tests and a separate critique/fix pass;
no live dbt/Snowflake or release qualification is implied.

Task 5 verification (2026-09-17):

- All commands used `UV_OFFLINE=1 uv --directory /Users/jdemlow/00_Code/github/dbt-cortex-agent run --no-sync` and the existing environment. No network, install, Snowflake, commit, or branch operations were performed.
- Initial focused run: 90 passed, 4 failed. Fixes preserved pre-connection endpoint ValueError and replaced context-manager-only response fakes with iterable/close HTTP response doubles. The next run passed 132 tests with two fake-resource finalizer warnings, fixed by fixture teardown.
- Expanded run after cleanup/command coverage: 257 passed in 1.19s with warnings treated as errors. Final focused/adjacent run: **446 passed in 7.23s**, `-q -W error`, across `test_eval.py`, `test_eval_verify.py`, `test_invoke.py`, `test_agent_commands.py`, `test_domain.py`, `test_cli.py`, `test_skills.py`, `test_deployment.py`, `test_lifecycle.py`, `test_identity_macros.py`, `test_fresh_manifest.py`, `test_requirements_contract.py`, and `test_compatibility_snapshot.py`.
- Focused Ruff: all checks passed on five implementation and four test files. Configured mypy: no issues in 12 source files. `git diff --check`: passed.
- Maker, critic, fix, and verifier passes were performed sequentially in this session, not by independent subagents. Critique caught EOF deadline bypass, HTTP incomplete-read classification, fake resource finalizer warnings, and human error visibility; fixes and behavioral tests cover each. No remaining blocking findings against this offline slice's criteria.
- Criteria 1-4 pass locally. No live connector compatibility, hard deadline, full-suite, dbt parse/compile, installed-wheel, mutation-test, or release qualification is claimed. The optional Snowflake connector is not present in the existing test environment; connector timeout propagation is verified with fakes only.

Contract notes: stream and accepted raw serialization each cap at 1,000,000
bytes, with 10,000 accepted events. Oversized input is rejected, not silently
truncated into a successful response. Valid earlier events survive; malformed,
unframed, over-limit, and HTTP exception partial bytes are not raw-event records.
Python invocation errors carry the partial normalized result and successful raw
path; CLI smoke retains them and exits 2. Raw files are opt-in and exclusive-create.
The monotonic duration now includes connector setup and cleanup, not just HTTP.
Blocking APIs and cleanup can overrun the budget; no remote cancellation is
claimed. Secondary cleanup errors attach to the primary exception; when no
primary exists, the first cleanup error is raised and later resources still close.

## Final Review Resource Closure (2026-09-18)

Objective: rejected HTTP requests release their owned response body without
losing the primary HTTP failure or the evidence available before failure.
Levers: register the raised `HTTPError` with the existing managed-resource stack;
retain the existing normalization and secondary-cleanup reporting. Data: real
stdlib `HTTPError` objects around synthetic response bodies. Assembly: acquire
connector/cursor -> reject HTTP request -> close body/cursor/connection -> retain
normalized failure and optional raw artifact.

Acceptance criteria:

- An `HTTPError` raised by `urlopen` is explicitly closed exactly once before
  cursor and connection cleanup, including when any or all closes fail.
- The identical HTTP exception remains the cause; close failures are secondary
  metadata, and available normalized/raw evidence is retained. An unaccepted
  HTTP body is not parsed as SSE or copied into raw-event evidence.
- Artifact-write failure cannot replace the HTTP primary or cleanup metadata.
  Existing partial-stream and programming-defect behavior remains unchanged.

Dependencies: REQ-031 managed-resource behavior and REQ-028 proof isolation.
Out of scope: new HTTP clients, cancellation guarantees, live operations,
installation/network, release/version changes, and unrelated existing edits.
Verifier: sequential maker, critic, fix, and offline verifier passes, not
independent subagents. Final results are recorded in REQ-028's final-review
supplement: 813 full-suite tests pass with 86.70% combined coverage; 132 focused
tests pass with warnings treated as errors. All three closure criteria pass
locally. Rejected bodies are not accepted events, so their raw artifact is empty;
prior accepted events on later stream failure remain covered by existing tests.
This does not complete pending live/release qualification.