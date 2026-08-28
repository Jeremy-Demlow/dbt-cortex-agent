# Changelog

This project had no public beta or stable release before `0.0.1`. Earlier Git
history records design experiments, not supported package versions.

## 0.0.6 — 2026-08-28

- Add generic preview-first Agent scaffolding with optional Analyst and evaluation
  capabilities; Semantic Views are not required and private-preview experimental
  mappings remain user-authored full-body YAML.
- Add package-native version inventory, promotion, rollback, version-specific
  smoke, and exact-confirmation Agent retirement while retaining dbt as the only
  Agent DDL authority.
- Make deployment content identity independent of serving DEFAULT so rollback
  and roll-forward reuse immutable versions without redundant commits.
- Replace oversized smoke output with a framed, normalized, bounded Agent SSE
  result and concise answer-first human rendering.
- Harden complete dependency authorization, finite evaluation values,
  pre-provisioned evaluation stages, evidence collisions, tracked requirements,
  installed-consumer guidance, lint, typing, and branch coverage.
- Remove orphaned legacy macros and fictional public macro documentation.

## 0.0.5 — 2026-08-27

- Resolve an explicitly supplied Snow CLI connection into dbt's environment for
  every command that parses, not only applied commands. Governed projects build
  `profiles.yml` from environment variables, so `agent deploy` and `eval verify`
  previews previously failed with a missing `SNOWFLAKE_ACCOUNT` parse error even
  when `--connection` was given. Resolution reads local Snow CLI configuration
  only; mutation, runtime, and spend still require explicit `--apply`.

## 0.0.4 — 2026-08-27

- Add package-native `agent deploy`, which previews or applies selected Agent
  deployment by validating physical identities and resource databases, uploading
  declared skills, and invoking the dbt dependency closure. The `cortex_agent`
  materialization remains the only Agent DDL authority.
- Add package-native `eval verify`, which materializes the eval model, revalidates
  the signed plan, executes native evaluation, consumes the exact candidate, and
  applies intrinsic thresholds or an accepted baseline.
- Add an explicit `--role` execution context and resolve Snow CLI credentials only
  for operations that connect, so previews no longer inspect authentication.
- Recognize `WORKLOAD_IDENTITY` alongside `SNOWFLAKE_JWT` when resolving a Snow
  CLI connection into the dbt child environment.
- Consumers no longer need copied Makefiles or Python sequencers for deployment or
  evaluation workflows; adopter tooling is limited to environment policy.

## 0.0.3 — 2026-08-24

- Support target-resolved manifests containing Agents and resources in multiple
  approved databases without a repository-global database assumption.
- Resolve Agent smoke, skill upload/smoke, and mutation guards from selected
  physical resource identities.
- Version evaluation plans at schema v2 with explicit Agent, table, stage,
  dataset/result, target, role, and warehouse identity.
- Namespace candidates, diagnostics, and baselines by target and physical Agent
  FQN to prevent cross-database collisions.

## 0.0.2 — 2026-08-19

- Treat persistent native evaluation partial completion as a transient platform
  failure and retry the complete evaluation under a new immutable run name.
- Require complete input and metric coverage before accepting a native evaluation
  result, and preserve sanitized expected/actual cardinality diagnostics.
- Keep raw Snowflake status details out of raised CLI errors while retaining
  allowlisted request, inference, error-code, and status evidence.

## 0.0.1 — 2026-08-18

- Added a Snowflake-only `cortex_agent` custom materialization. The dbt model
  body is the Agent specification; `dbt compile` validates it and `dbt build`
  owns creation, immutable versions, aliases, profile, and comments.
- Added manifest-driven skill planning, upload to an existing infrastructure-
  managed stage, and live skill smoke proof.
- Added optional evaluation planning, paid execution, polling, result artifacts,
  threshold and baseline gates, and explicit baseline acceptance.
- Added the fixed synthetic Orders starter and installed-wheel/dbt compatibility
  verification for dbt Core 1.10 and 1.11.
