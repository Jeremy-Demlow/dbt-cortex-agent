# REQ-004: Lifecycle and safety hardening

## Summary

Fail closed across manifest discovery, Snowflake identity, local evaluation artifacts, mutation context, skill smoke, and idempotent alias reconciliation.

## Business context

The Python companion and dbt macros cross security- and cost-sensitive boundaries. Stale manifests, permissive identifiers, path traversal, ambiguous Agent mapping, database drift, and implicit connections can target the wrong object or preserve misleading evaluation evidence without producing an immediate syntax error.

## Objective

Consumers can run lifecycle and evaluation tooling without stale metadata, ambiguous identity, unsafe local paths, or mismatched Snowflake context reaching a mutation, paid evaluation, or accepted baseline.

## Acceptance criteria

1. Manifest eval discovery selects only non-empty `cortex_eval` mappings whose `enabled` value is not `false`, with duplicate suite selection rejected by the existing exact selector.
2. Evaluation result collection retries both empty and unscored responses to a configured bound, then fails closed.
3. One shared Python module validates supported unquoted Snowflake identifiers, FQNs, stage paths, Agent objects, aliases, versions, roles, and warehouses at external boundaries; grant macros apply the same unquoted-role grammar before rendering SQL.
4. Candidate and baseline artifact components are safe slugs, resolved paths remain contained by their configured roots, and loaded candidate/baseline documents satisfy an explicit versioned schema before compare, gate, or acceptance.
5. Manifest-dependent CLI operations run `dbt parse` before loading `target/manifest.json` by default. `--no-parse` is an explicit fixture-only escape hatch whose help and documentation warn against normal use.
6. Before skill upload, Agent mutation, or paid evaluation, the configured Python database equals the database resolved by dbt for the active target.
7. Mutating and spend-bearing CLI operations require `--connection` to be explicitly supplied; an environment-only connection is insufficient.
8. Skill smoke maps every selected logical Agent to its own physical object from manifest naming. `--agent-object` is allowed only when exactly one logical Agent is selected.
9. An unchanged deploy reconciles an explicitly requested alias to the current default version without committing a new version.
10. Package guidance does not direct consumers to repository-only `make dbt-focus-*` targets.
11. Direct Agent invocation has a bounded HTTP timeout and rejects malformed or unterminated SSE instead of silently returning partial output.
12. Focused and full Python tests, static guards, package build, and dbt parse pass without live mutation or paid evaluation.

## User stories

- As a package consumer, I receive fresh manifest-owned Agent and eval metadata before lifecycle tooling acts.
- As a platform owner, I can prove mutation and spend target the explicitly selected connection and the database dbt resolved.
- As an evaluation maintainer, I cannot accept path-traversing, malformed, or schema-incompatible result artifacts.
- As an Agent owner, skill smoke invokes the physical Agent corresponding to each logical exposure.
- As a release operator, I can reconcile a requested alias on an unchanged deploy without minting a redundant version.

## Dependencies

- REQ-002 dbt/Python ownership boundary.
- REQ-003 explicit bootstrap configuration.
- Existing manifest-owned Agent/eval definitions and dbt lifecycle macros.

## Out of scope

- Refactoring the rendered evaluation-plan ownership boundary.
- Supporting quoted or case-sensitive Snowflake identifiers.
- Live Agent mutation, skill upload, smoke invocation, or paid evaluation.
- Changing evaluation metrics, thresholds, or baseline ratchet policy.

## Notes

- Objective lever: validate identity and context once at each external boundary, then reuse normalized values internally.
- Data proof: existing manifest fixtures, command fakes, cursor fakes, and artifact fixtures cover every requested failure mode without remote state.
- Assembly line: parse -> load manifest -> validate identity/context -> plan -> dry-run or guarded mutation/spend -> validate versioned artifact -> compare/gate/accept.
- Reversible local choice: artifact schema version `1` is introduced for both candidates and baselines; legacy unversioned artifacts fail closed rather than being guessed or migrated implicitly.
- Reversible local choice: `--no-parse` is shared by manifest-dependent subcommands but is documented as controlled-fixture-only.
- Reversible local choice: skill smoke requires `naming.<target>` when a target is active; it does not guess macro environment suffix vars from `snowflake_name`.
- Verifier: full pytest, source/static guards, package build, and integration-consumer `dbt parse`; all remote operations use fakes and dry-run remains the default.
- Critic: no blocking findings after requiring `naming.<target>` for smoke and validating loaded artifact identity slugs.
- Verification on 2026-08-04: all 91 Python tests passed; lifecycle/guidance static guards and `git diff --check` passed; `uv build` produced the v0.3.0 source distribution and wheel; dbt 1.11.11 freshly parsed the integration consumer with partial parsing disabled and inert non-connecting profile placeholders. No live operation or paid evaluation ran.
