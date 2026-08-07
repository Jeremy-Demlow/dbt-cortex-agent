# Changelog

All notable package changes are recorded here. The package follows semantic
versioning for documented public macros, metadata contracts, and rendered specs.

## Unreleased

## 0.3.1 — 2026-08-07

- Added explicit `canonical`/`native_eval` selection to Agent render and deploy,
  with canonical defaults, macro validation, dbt-owned physical identity,
  strict marked-output parsing, and deterministic contained render artifacts.
- Native-eval CLI deploy retains the existing apply safety gates while skipping
  canonical-only skill planning and upload.
- Added skill-independent `agent smoke` preview and explicit runtime invocation,
  with manifest-owned physical resolution, optional exact tool assertion, stable
  structured output, existing SSE-client reuse, and pre-invocation safety gates.
- General Agent smoke now selects `canonical` or `native_eval`, reports that
  projection, and resolves native-eval physical identity through dbt rendering.

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
- Corrected package guidance for the shipped v0.3.0 contract: init configures but
  does not scaffold existing dbt projects, Snow CLI is a prerequisite, applied
  canonical CLI deploy uploads declared skills, native-eval deployment uses the
  public macro, and CLI/macro output, safety, artifact, and troubleshooting
  boundaries are documented explicitly.
- Added preview-first `init --starter orders` generation from packaged integration
  fixtures, with exact structured actions, atomic collision validation,
  idempotent identical files, `.dbtignore` append, and semantic-view dependency
  preservation. Projection, render, deploy, and smoke behavior are unchanged.

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
