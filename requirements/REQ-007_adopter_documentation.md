# REQ-007: complete adopter documentation

## Summary

Publish v0.3.0 documentation as a tested release surface for installing, configuring,
validating, deploying, evaluating, operating, and upgrading `dbt_cortex_agent`.

## Business context

The package now ships one dbt surface and one Python CLI surface at the same version,
but adopter guidance still mixes package macros with repository-only copied tooling,
inherits obsolete defaults, and does not present the CLI's mutation, spend, output, and
exit contracts in one place. An adopter must be able to follow the release docs without
reading source code or assuming unsupported orchestration.

## Objective

An adopter can reach a locally validated v0.3.0 project in five minutes, understand the
exact boundary before mutation or evaluation spend, and select either the shipped CLI or
public dbt macros without encountering stale or contradictory instructions.

## Acceptance criteria

1. The root README is concise and operational: product identity, two install surfaces at
   one version, compatibility, five-minute non-mutating quickstart, controlled deploy,
   CLI-versus-macro ownership, lifecycle/evaluation overview, docs map, limitations, and
   project policies.
2. Installation and upgrade guidance covers the public HTTPS-tagged dbt Git package plus the
   Python distribution, the single `runtime` extra, compatibility, source-install fallback,
   and migration from pre-v0.3 releases/former extras. PyPI commands are explicitly post-publication.
3. A standalone quickstart uses the shipped CLI, fresh manifest behavior, explicit target
   and database allowlists, and no `--apply`, Agent commit, live runtime call, or paid eval.
4. Configuration documentation defines exposure and eval metadata, dbt vars, CLI flags,
   environment variables, and the precedence `CLI > environment > built-in default`.
5. Lifecycle, skills, and evaluation guides identify dbt as the definition/deploy system
   of record, distinguish CLI and macro paths, and state prerequisites, native-eval Agent,
   table/stage identity, spend, artifact, provenance, threshold, and baseline behavior.
6. CI guidance separates non-spend PR checks, controlled sandbox deployment, and explicit
   paid-evaluation opt-in without claiming that CLI eval creates its Agent, dataset table,
   stage, or other native evaluation prerequisites.
7. Snowflake setup documents deploy, runtime, skill, and evaluation access responsibilities
   in a security matrix; troubleshooting begins with `dbt-cortex-agent doctor`.
8. A complete CLI reference is derived from the shipped parser and documents every command,
   option, environment input, output mode, exit code, and mutation/runtime/spend label.
9. Architecture, end-to-end flow, integration proof boundaries, and progressive examples
   use the installed CLI rather than copied scripts or repository-only Make targets.
10. Automated documentation drift tests verify parser command/option coverage, stale phrase
    removal, local links, v0.3.0 identity, parseable metadata examples, and quickstart safety.
11. Documentation tests, the full Python suite, package build, and offline integration dbt
    parse pass without commit, live Snowflake mutation, runtime invocation, or paid evaluation.
12. The dbt package tag and Python distribution use the same immutable `0.3.0` release identity;
    `doctor` is documented as the local alignment check, and automated guards reject SSH/private
    install wording or drift from the public HTTPS tag and pinned Python commands.

## User stories

- As a new adopter, I can install both product surfaces and validate a project without
  mutating Snowflake.
- As a platform owner, I can identify each privilege and explicit apply/spend boundary
  before granting access or running automation.
- As an automation author, I can rely on documented commands, outputs, and exit codes that
  are checked against the shipped parser.
- As an upgrader from a pre-v0.3 release, I can remove copied tooling and retired extras.
- As an installer, I can distinguish commands available after PyPI publication from the public
  tagged source fallback available now.

## Dependencies

- REQ-002 v0.3.0 identity and Python ownership.
- REQ-003 explicit bootstrap configuration.
- REQ-004 lifecycle and safety hardening.
- REQ-005 dbt-rendered evaluation execution plan.
- REQ-006 stable domain-oriented CLI.

## Out of scope

- New CLI commands, macros, Agent/eval semantics, or Snowflake objects.
- Agent commit, alias movement, live mutation, runtime invocation, or paid evaluation.
- Package publishing automation or repository visibility changes.

## Notes

- Objective lever: replace repository-history documentation with an adopter journey whose
  examples are generated from or tested against the released parser and manifest contracts.
- Data proof: the argparse tree, package metadata, macro signatures, integration manifest,
  and existing lifecycle/eval tests provide local sources for every documented contract.
- Assembly line: install -> configure -> doctor/manifest validate -> render/plan -> explicit
  sandbox apply -> optional native evaluation -> local gate/baseline evidence.
- Reversible local choice: keep focused pages under the existing `docs/` hierarchy and add
  quickstart, configuration-model, and CLI reference pages rather than a new docs framework.
- Reversible local choice: make `pipx` with the `runtime` extra the primary CLI recommendation,
  retain a pip equivalent for managed environments, and use the public `v0.3.0` Git tag for dbt
  plus the Python source install after release. No package publication or repository visibility
  is changed by this slice.
- Ask-first decision: because the public `v0.3.0` tag does not yet exist, the user selected the
  current commit SHA as the immutable source-install-now fallback for environments with repository
  access; public release-tag examples remain `v0.3.0` and become runnable when that tag is published.
- Verifier: full local documentation tests, Python tests, package build, and offline
  integration `dbt parse`; no live proof is permitted because this slice changes docs/tests
  only and explicitly excludes mutation, runtime invocation, and spend.
- Critic: no blocking findings remain after expanding drift coverage to integration docs
  and parser-valid examples, requiring explicit eval warehouse documentation, correcting
  evaluation-stage configuration, and avoiding assumptions about a public Python index.
- Verification on 2026-08-04: 173 Python tests passed, including 56 documentation contract
  tests; `git diff --check` and Python byte-compilation passed; `uv build` produced the
  v0.3.0 sdist and wheel; and the integration consumer completed dependency installation
  plus offline `dbt parse --no-partial-parse` with dbt 1.11.11/dbt-snowflake 1.11.4 and an
  intentionally nonexistent key path. No connection, Agent commit, live mutation, runtime
  invocation, paid evaluation, baseline movement, or git commit was performed.
- Verification on 2026-08-05: all 184 Python tests passed; Python byte-compilation,
  `git diff --check`, Twine metadata checks, wheel inventory, local Markdown links, and the
  private/SSH install-reference scan passed; `uv build` produced the v0.3.0 sdist and wheel;
  and dbt 1.11.11/dbt-snowflake 1.11.4 completed integration dependency resolution plus
  offline parse. The pinned source SHA is advertised by the authenticated HTTPS remote.
  Anonymous GitHub metadata links still return 404 because repository visibility and the
  `v0.3.0` tag remain intentionally unchanged; those links become public release surfaces
  only when the repository/tag are published. No workflow, visibility, Snowflake state,
  package publication, or git commit was changed.
- Documentation correction on 2026-08-07: the shipped v0.3.0 guidance now states
  that init configures existing dbt projects without scaffolding resources, Snow CLI
  is required, canonical CLI deploy uploads declared skills before macro deploy,
  native-eval deployment is a direct guarded macro prerequisite, CLI and direct-macro
  safety/output behavior differ, and candidate/baseline paths plus troubleshooting
  order are explicit. The integration fixture now uses its documented sandbox database
  as a non-empty allowlist so doctor validates rather than intentionally fails.
