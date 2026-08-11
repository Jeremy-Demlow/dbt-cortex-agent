# REQ-005: dbt-rendered evaluation execution plan

## Summary

Make one schema-versioned dbt macro payload authoritative for evaluation identity, native config, metric policy, dataset/stage context, execution role, and deterministic suite signature inputs, including safe migration of known legacy accepted evidence.

## Business context

Python currently reconstructs Agent naming, dataset identity, native evaluation config, and metric policy already owned by dbt macros. That duplicate authority can silently evaluate a different object or policy than dbt validated, and a candidate can currently widen accepted baseline regression tolerances.

## Objective

Evaluation evidence is reproducibly tied to one dbt-validated execution plan and one stable Agent version, while Python remains a transport, polling, artifact, comparison, and explicit migration client rather than a second metadata renderer.

## Acceptance criteria

1. A public or internal dbt macro emits exactly one machine-readable JSON plan with an explicit schema version for one logical Agent and suite.
2. The plan reuses authoritative dbt macros for eval/Agent validation, target Agent FQN, dataset FQN, native eval config, metrics, thresholds, regression policy, stage/config path, target/database context, and ordered declared ground-truth refs.
3. The plan renders without querying or mutating Snowflake and has a deterministic suite signature over plan identity, native metrics/config policy, thresholds, tolerance policy, and ordered refs.
4. Python obtains and validates the plan through the package-qualified `dbt_cortex_agent.cortex_eval__execution_plan` run-operation after fresh parse; injectable plan/command fakes remain supported.
5. Python no longer resolves physical Agent naming, dataset FQN, metric contract, or native eval config independently.
6. Table validation rejects missing or duplicate `ground_truth_ref` values and duplicate `INPUT_QUERY` values; result annotation joins through the unique stable ref contract rather than a lossy question-text map.
7. Python captures Agent alias/version provenance immediately before START and after completion, evaluates the pre-start DEFAULT, and marks the result indeterminate/fails closed if DEFAULT changes.
8. Candidate and baseline artifacts use a documented versioned schema containing plan schema/signature, ordered refs, metric/threshold/tolerance policy, and pre/post provenance.
9. Compare and gate use the accepted baseline tolerance policy; a candidate cannot widen it, and suite or policy signature changes fail closed.
10. Evaluation dependency errors identify the consolidated eval extra, and expected CLI validation/runtime errors return controlled exit code `2` without tracebacks.
11. Focused/full tests, package build, dbt parse, and macro structural/offline tests pass without Agent commit, live mutation, or paid evaluation.
12. `eval run` exposes the shared repeatable target/database allowlists and, before connector construction, rejects applied execution unless the dbt-rendered plan target and database match both the configured context and those allowlists.
13. The dbt-rendered plan supplies the authoritative target role; applied execution sets `USE ROLE` before warehouse, database, and schema, and the CLI plan payload exposes that role.
14. A local migration path recognizes only the documented legacy accepted-artifact shape, uses a freshly rendered current plan for schema-v2 identity, metric policy, thresholds, tolerances, ordered refs, and suite signature, and preserves legacy summary/run provenance.
15. Legacy migration is preview-only by default, writes only with `--apply`, targets an explicit or new baseline directory, and refuses an existing destination unless `--force` is also explicit. It never invokes a connector or paid evaluation.

## User stories

- As an evaluation maintainer, I can inspect one dbt-rendered plan that exactly identifies what will be evaluated and under which policy.
- As a release operator, I can prove a candidate used one stable DEFAULT version for the complete run.
- As a baseline owner, a candidate cannot relax the accepted regression policy to pass its own comparison.
- As an evaluation operator, an applied run cannot connect until its dbt-rendered target and database are explicitly allowlisted, and it executes under the role dbt resolved.
- As a baseline owner, I can preview a deterministic migration of known legacy accepted evidence without silently overwriting a current baseline or paying for a new evaluation.

## Dependencies

- REQ-002 dbt/Python ownership boundary.
- REQ-004 fresh parse, context, and artifact safety.
- Existing Agent/eval validation, naming, dataset, config, and stage macros.

## Out of scope

- Agent deployment, commit, alias movement, or promotion.
- Live Snowflake evaluation or paid metric execution.
- Supporting ambiguous datasets without stable unique ground-truth refs.
- Guessing unknown legacy artifact shapes or deriving current policy from legacy evidence.

## Notes

- Superseded physical-identity assumption (2026-08-10): REQ-013 supersedes this requirement's use
  of a distinct physical evaluation Agent as a future contract. The execution-plan, evidence,
  provenance, and baseline-policy facts remain historical requirements, but future evaluation plans
  must identify the enabled exposure's single target-resolved Agent FQN.
- Objective lever: make dbt's validated execution plan the only metadata authority consumed by Python.
- Data proof: the integration consumer already declares ordered `ground_truth_ref` values and all required metric, threshold, target, dataset, and Agent metadata.
- Assembly line: fresh parse -> dbt plan render -> Python plan validation -> table validation -> pre-start provenance -> start/poll/retry/fetch -> post provenance -> artifact -> baseline-owned compare/gate.
- Reversible local choice: plan schema version is `1`; artifact schema version advances to `2` and legacy v1 artifacts fail closed.
- Reversible local choice: the deterministic suite signature hashes canonical JSON containing plan identity, native config, metrics, thresholds, tolerances, and ordered declared refs.
- Reversible local choice: DEFAULT drift produces an indeterminate failed candidate rather than attributing results to either version.
- Reversible local choice: the plan remains schema version `1`; `target_role` is added to the signed identity and is required by current plan parsing.
- Reversible local choice: migration accepts only an unversioned or schema-v1 accepted artifact with safe identity slugs, `passed: true`, a numeric metric summary, and mapping run metadata; all current contract fields come from the dbt-rendered plan.
- Reversible local choice: migrated provenance is stored under `run_metadata.legacy_migration`, including the source path, legacy schema/type/run fields, and the complete legacy run metadata. Stable schema-v2 provenance uses the legacy evaluated/default version when present, otherwise the explicit `LEGACY_UNKNOWN` sentinel.
- Reversible local choice (2026-08-11): the CLI qualifies its package-owned execution-plan macro as `dbt_cortex_agent.cortex_eval__execution_plan`. This removes consumer namespace/dispatch ambiguity while preserving the public unqualified macro for direct dbt usage. dbt 1.12 is regression evidence within the existing `>=1.10,<2.0` support range, not a widened support claim.
- Verifier: full pytest, policy/documentation/CLI contract tests, Python byte-compilation, package build, wheel inventory, integration-consumer dependency resolution and offline dbt parse, plus macro structural checks. Credential-free compile remains excluded because the semantic-view adapter path authenticates even with `--no-introspect`.
- Critic on 2026-08-06: no blocking findings remain after making existing-target preview non-mutating but inspectable, requiring exact current-plan metric coverage, rejecting non-finite legacy scores, and keeping apply-time overwrite protection explicit.
- Verification on 2026-08-06: all 210 Python tests, 154 deterministic package/Agent/eval contracts, and 73 documentation/CI contracts passed; Python byte-compilation and `git diff --check` passed; `uv build` produced both v0.3.0 distributions and wheel inventory verification passed; dbt Core 1.10.22/dbt-snowflake 1.10.3 and dbt Core 1.11.12/dbt-snowflake 1.11.4 resolved dependencies and parsed the integration consumer offline with partial parsing disabled. Generated residue was removed. No connector, live Snowflake operation, Agent mutation, or paid evaluation ran.
- Verifier: direct maker/critic/fix/verifier passes, full pytest/build, integration-consumer dbt parse, and macro structural/offline checks. No paid evaluation or live mutation.
- Critic: no blocking findings remain after sharing the authoritative native-config renderer, treating SQL table order as undefined, validating malformed plan identity, enforcing artifact provenance, and making baseline policy authoritative.
- Verification on 2026-08-04: all 98 Python tests passed; `git diff --check` passed; `uv build` produced the v0.3.0 source distribution and wheel; dbt 1.11.11 parsed the integration consumer with partial parsing disabled and rendered one schema-v1 `CORTEX_EVAL_PLAN_JSON` with the expected target Agent, dataset, config, metrics, thresholds, ordered refs, and suite signature using inert non-connecting profile placeholders. No live Snowflake operation or paid evaluation ran.
