# Changelog

All notable package changes are recorded here. The package follows semantic
versioning for documented public macros, metadata contracts, and rendered specs.

## Unreleased

- No changes yet.

## 0.3.1 — 2026-08-07

- Added preview-first `init --starter orders` generation from packaged synthetic
  fixtures, with exact structured actions, atomic collision validation,
  idempotent identical files, `.dbtignore` append, and semantic-view dependency
  preservation.
- Agent render and deploy resolve one target-selected physical Agent, with macro
  validation, strict marked-output parsing, deterministic `spec.json` artifacts,
  and complete skill/capability rendering.
- Added skill-independent `agent smoke` preview and explicit runtime invocation,
  with manifest-owned physical resolution, optional exact tool assertion, stable
  structured output, existing SSE-client reuse, and pre-invocation safety gates.
- General Agent smoke resolves the same manifest-owned physical Agent as deploy.
- Added a project-local, script-free Cortex Code adoption skill for dbt-owned
  Agents. It supports existing semantic views, the fixed Orders starter,
  existing-Agent migration, and optional eval authoring with manual command
  parity and separate local-write, Snowflake, paid-eval, and baseline approvals.
- Doctor now accepts an immutable 40-character Git SHA only when the installed
  consumer dbt package metadata matches the CLI version. Branches, missing or
  mismatched installed metadata, and semantic-version mismatches fail closed.
- Evaluation metadata is optional and targets the same deployed Agent; it does
  not create, deploy, clone, suffix, or filter a second Agent.
- Replaced the evaluation-specific duplicate Agent contract with one full
  Agent per enabled exposure and target. Optional suites evaluate that same Agent and
  never deploy or mutate a second object.
- Updated the Orders starter, project-local Cortex Code skill, active docs, and
  package tests for Agent-only and Agent-plus-eval adoption. Historical `_EVAL`
  evidence remains auditable but is explicitly superseded.
- The Python 0.3.1 distribution is not yet published to PyPI; active install
  guidance uses a reviewed clean local checkout until publication is verified.

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
