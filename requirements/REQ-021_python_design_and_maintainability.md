# REQ-021: Python Design and Maintainability

**Status:** Complete (`0.0.6`)

## Summary

Make `src/dbt_cortex_agent` a small, typed, inspectable control-plane library. Use standard-library values and protocols rather than adding fastcore as a runtime dependency, while adopting its emphasis on concise composition, deliberate APIs, and executable examples.

## Acceptance Criteria

1. External manifest, YAML, JSON, subprocess, connector, and HTTP payloads are validated at typed boundaries before domain logic uses them.
2. Snowflake identities, execution context, lifecycle phases, policies, and outcomes use immutable values with centralized validation.
3. Orchestration functions compose short single-purpose functions; command handlers do not contain reusable domain logic.
4. Expected configuration, filesystem, subprocess, connector, HTTP, and protocol failures produce categorized controlled errors without tracebacks.
5. Every subprocess and network operation has a finite, configurable bound and reports command phase without exposing secrets.
6. Public exports and function signatures are intentional, documented, and covered by installed-wheel import tests.
7. Every tracked test is collected by default; intentional live or slow exclusions use explicit markers rather than ignore paths.
8. CI enforces formatting/linting, supported Python typing, branch coverage, complexity bounds, dependency compatibility, wheel inventory, and secret scanning.
9. Property tests cover identifiers, paths, numeric policies, and protocol framing; mutation tests target safety-critical validators and gates.
10. Compatibility snapshots record the supported `0.0.5` CLI, JSON, artifact, and macro behavior before replacement work begins.

## Non-Goals

- A fastcore runtime dependency.
- A general web framework or dataframe dependency.
- Compatibility wrappers for APIs that were documented but never implemented.

## Evidence

Offline qualification on 2026-08-28: 315 tests passed with 81.35% branch
coverage; Ruff formatting/lint/C90 and mypy passed; all six bounded
safety-critical mutants were killed.

`TC-021-01` through `TC-021-10` in `tests/test_cases.md`.