# REQ-033: Configurable Runtime Budget and Engineer Handoff

**Status:** 0.0.12 implementation; final exact-release qualification and publication pending.

## Objective

Operators can run a longer investigation through the public CLI without editing
installed code, and diagnose a failed invocation without silently retrying it.

## Acceptance Criteria

1. Agent and skill smoke expose `--timeout-seconds`, default 60 for compatibility.
   Values must be finite and positive, including fractional seconds. Invalid
   values fail before runtime acquisition. Python `invoke_agent(timeout=...)`
   remains compatible; skill smoke forwards a fresh budget for each invocation.
2. Preview and applied JSON expose `timeout_seconds`. Normalized runtime metadata
   records `client_timeout_seconds` even when server metadata conflicts. The
   budget includes setup and streaming, not dbt parsing, evaluation polling, or
   the aggregate duration of several skill invocations. Heartbeats do not renew it.
3. Controlled failures retain partial normalized evidence and elapsed duration.
   Skill smoke retains prior verified skills and the failing skill's identity
   and response, exits 2, and does not invoke remaining skills. Unexpected
   programming errors still propagate. No automatic retries or cancellation claim.
4. Synthetic fake-clock tests distinguish an 80-second completion under a
   default 60-second budget from success under an explicit larger budget. Both
   CLI paths have validation, forwarding, preview and failure-evidence coverage.
5. Public installation, CLI and engineer guides identify matching 0.0.12
   interfaces, distinguish pending publication from historical 0.0.11 evidence,
   and explain timeout recovery and cost boundaries.
   Operators do not require private adopter scripts. Documentation commands parse.

## Limits and release boundary

The client uses cooperative deadline checks; blocking I/O, authentication,
retries and resource cleanup can overrun. Closing a connection does not prove
server cancellation or that charges stopped. Raising the budget does not repair
incorrect answers. Reference incident quality is a separate adopter requirement.

Existing 0.0.11 artifacts and old failures remain immutable. New candidate,
published-install and live qualification are separate gates. No new live budget,
baseline acceptance, canonical mutation, release tag or publication is authorized
by these local implementation criteria.

The separately approved 2026-10-30 release-finalization slice in REQ-021 updates
current installation pins and documentation only. It does not turn earlier
candidate checks into exact-final-release proof or grant this worker Git or
native execution authority; the parent owns those release steps.

## Verification

Focused runtime/command/parser tests, full product tests, lint/type checks and
supported-line installed-wheel consumers. Live and successor publication status
must be recorded separately; offline tests are not native runtime proof.