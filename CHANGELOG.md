# Changelog

This project had no public beta or stable release before `0.0.1`. Earlier Git
history records design experiments, not supported package versions.

## 0.0.11 — 2026-10-09

Candidate pending qualification and publication; this heading is not release proof.

- Fix explicit DEFAULT pinning when `agent promote --set-default` or
  `agent rollback --set-default` targets the version DEFAULT already resolves
  to. Always issue the explicit SET after identity, version, and stale-state
  checks; an implicit DEFAULT otherwise follows the next commit. Alias-only
  routing remains unchanged. This fix is not part of the immutable `v0.0.10`
  release and needs successor-release qualification.
- Strengthen exact-wheel live qualification with same-value DEFAULT pinning
  before a changed commit and inspected intermediate routes. Refuse mismatched
  sessions and existing reserved objects. Preserve failed observations, verify
  cleanup absence, and stop automatic cleanup/retry when server state is unknown.

## 0.0.10 — 2026-10-08

Published on 2026-10-08. Its immutable artifacts remain available; the later
walkthrough exposed the equal-value DEFAULT defect corrected by the successor.

- Add `--version VERSION$N` to `eval run` and `eval verify` to score one
  committed Agent version. The version is staged per run, checked before START,
  and recorded as `requested_version` and `evaluated_version`; a DEFAULT move no
  longer voids a pinned run.
- Accept pinned system metric judges (`{name, version}`) and a custom metric
  `model`. Candidates record `metric_judges`, and comparison refuses runs scored
  by different judges.
- Record what Snowflake ran, not what was requested: `evaluated_version` and
  `observed_metric_judges` come from the run's trace spans. A run that traces
  another version, or none, is `indeterminate`; comparison prefers observed
  judges, so a `v3` selector that resolved to a different minor version is
  caught.
- **Breaking:** stage skills default to `immutable`. Each deploy uploads a
  skill to a content-addressed `<path>/sha256-<digest>` folder, reads it back
  before dbt build, and commits that path, so rolling an Agent back also rolls
  back its skill text. Snowflake reads skills live; previously every version read
  the same overwritten folder. Declare `mode: overwrite` for the earlier
  behavior, or a `git_integration` skill pinned to a tagged `commits/<sha>`.
  Direct `dbt build` of an immutable skill now needs the `dbt_vars` printed by
  `skill upload --apply`.
- Remove the documented `cortex_agent_validate_staged_skills` var; nothing read it.
- `agent deploy` selects each Agent by its full manifest fqn. `+<name>` also
  matched a dbt project of the same name and built its other Agents (the
  expected-FQN guard stopped them). A successful build that does not reconcile
  every planned Agent now fails instead of reporting `verified`.
- Ship the corrected repository-local adoption skill in the release tag; it now
  describes skill modes.

## 0.0.9 — 2026-09-18

Published on 2026-09-18 after protected exact-wheel qualification and PyPI
trusted publishing ([release workflow](https://github.com/Jeremy-Demlow/dbt-cortex-agent/actions/runs/35400838944)).

- Bind deployment, routing, retirement, and fresh-manifest consumption to resolved
  Agent identity, including default dbt schema generation.
- Reject incomplete, non-finite, duplicate, drifted, or otherwise ineligible
  evaluation evidence before quality gates or baseline acceptance.
- Repair LIVE on unchanged retries and preserve per-Agent/per-destination durable
  outcomes; align explicit skill metadata and approved-role propagation.
- Retain bounded partial runtime and candidate evidence on failure, distinguish
  execution from gate failure, and independently clean up acquired resources.
- Close HTTPError-owned response bodies without masking primary failures or
  secondary cleanup evidence; pin all proof child environments to isolated dbt.
- Replace comment-token governance with collected proof links and explicit gaps.
- Correct grant, role, skill, and effect-boundary guidance; retain both database
  observations and independent cleanup outcomes in live-proof attestations.
- The release's exact wheel passed protected multi-database lifecycle proof;
  paid native Agent Evaluation is separate and was not part of that release gate.
  Version 0.0.8 and its immutable tag remain unchanged.

## 0.0.8 — 2026-09-09

- Centralize controlled operational failure classification across deployment,
  routing, and evaluation while preserving programming-defect propagation.
- Reuse one routing state-inspection helper for durable partial-failure evidence.
- Add direct classifier and governance evidence without changing Agent DDL, CLI
  behavior, or lifecycle ordering.

## 0.0.7 — 2026-09-03

- Fix the public dbt evaluation macro path by removing unreachable legacy
  branches and undefined macro calls, and validate evaluation run names before
  SQL interpolation.
- Preserve normalized Agent smoke evidence when an expected-tool assertion
  fails, while retaining the controlled runtime exit contract.
- Reject an existing raw-event destination before invoking the Agent.
- Stop classifying unexpected programming defects as controlled durable
  operation failures.
- Clarify multi-database safety: connection context and manifest-derived
  resource authorization are independent controls.

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
