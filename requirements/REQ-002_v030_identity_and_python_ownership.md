# REQ-002: v0.3.0 identity and Python ownership

## Summary

Establish v0.3.0 as the combined dbt package and Python companion release, with one explicit ownership boundary between dbt and Python.

## Business context

Consumers need one product identity and one lifecycle authority. The Python companion may coordinate local and remote operations, but it must not duplicate Agent lifecycle DDL already owned by dbt macros.

## Objective

Consumers can adopt v0.3.0 without ambiguity about which layer defines or mutates Cortex Agent lifecycle state.

## Acceptance criteria

1. At completion of this historical requirement, package, runtime, lock, bootstrap, citation, and installation references identified v0.3.0; later release requirements supersede only the active version wording.
2. The v0.3.0 changelog entry records the combined dbt package and Python companion product.
3. A concise architecture document assigns graph/meta contracts, rendering, Agent DDL, naming, versions, aliases, grants, and eval-plan rendering to dbt; it assigns local files, Snow CLI coordination, REST/SSE, polling/retry, local artifacts/baselines, and thin macro delegation to Python.
4. Python Agent deploy, grant, promotion, and rollback paths delegate lifecycle changes to dbt macros.
5. Python source contains no mutating `CREATE AGENT`, `ALTER AGENT`, or `DROP AGENT` DDL.
6. `dbt_cortex_agent.eval` no longer advertises premature importable lifecycle exports, while CLI imports from internal eval modules continue to work.
7. Focused Python tests and available dbt parse/compile checks pass.

## User stories

- As a package consumer, I can identify the dbt and Python components as one v0.3.0 product.
- As a maintainer, I can tell which layer owns each lifecycle concern and prevent Python from becoming a second Agent DDL implementation.

## Dependencies

- Existing dbt Agent lifecycle macros.
- Existing Python CLI and manifest-driven orchestration.

## Out of scope

- Correcting hardcoded init source/default behavior.
- Refactoring evaluation execution behavior.
- Changing Agent metadata, rendered specs, or live Snowflake objects.

## Notes

- This slice makes only reversible package-local changes and performs no live deployment or paid evaluation.
- Verifier: focused pytest plus dbt parse/compile when the recovered environment permits them.
- Verification on 2026-08-04: 62 Python tests passed; Python source/wheel build produced v0.3.0 artifacts; dbt dependency resolution and parse passed. dbt compile reached adapter initialization but could not continue without a valid Snowflake private key, so compile remains environment-blocked rather than verified.
