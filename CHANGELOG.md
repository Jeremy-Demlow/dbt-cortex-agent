# Changelog

All notable package changes are recorded here. The package follows semantic
versioning for documented public macros, metadata contracts, and rendered specs.

## 0.3.0 — 2026-08-06

- Combined the dbt package and Python companion under one versioned product.
- Defined the dbt/Python ownership boundary: dbt owns graph contracts, rendering,
  Agent lifecycle DDL, naming, versions, aliases, grants, and eval-plan rendering;
  Python owns local and remote coordination, polling/retry, and local artifacts.
- Added guards that keep Python Agent lifecycle operations delegated to dbt macros
  and prohibit mutating Agent DDL in Python source.
- Removed premature convenience exports from `dbt_cortex_agent.eval`; CLI imports
  remain internal and explicit.
- Documented the public distribution contract: the Python CLI will install from
  PyPI after v0.3.0 publication, the dbt package installs from the matching public
  HTTPS `v0.3.0` Git tag, and an immutable commit supports source installation in
  environments with repository access before the release is published.
- Hardened paid evaluation with explicit target/database allowlists and the
  authoritative dbt-rendered role, and added preview-first migration of known
  legacy accepted baselines to schema v2 without live evaluation.

## 0.2.0 — 2026-07-31

- Added package-owned adoption documentation and detailed ASCII architecture flows.
- Added a canonical package-local starter consumer verified independently from the
  full ski-resort reference project.
- Added public Agent/eval metadata, macro, variable, compatibility, and upgrade contracts
  with implementation drift guards.
- Qualified dbt Fusion 2.0.0-preview.203 as advisory and documented its missing macro
  dependency edge; dbt Core remains authoritative.
- Added selected-Agent skill planning, shared-skill deduplication, fail-closed
  upload-before-canonical-deploy orchestration, and Agent-scoped smoke verification.
- Added active non-spend package/starter release CI and separated package-only from
  full-framework workflow templates.
- Preserved all existing canonical/native-eval reference Agent specification snapshots.

## 0.1.0 — 2026-07-29

- Extracted Agent and evaluation macros into an installable local dbt package.
- Added exposure-based Agent validation and deterministic canonical/native-eval rendering.
- Added sandbox-guarded LIVE/version/alias lifecycle with spec and skill hashing.
- Added Agent-object usage grants, staged skills, MCP attachment, and eval macros.
- Added the `cortex_eval_question_coverage` generic test.
