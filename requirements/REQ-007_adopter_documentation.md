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
2. Installation and upgrade guidance covers the pinned dbt Git package plus Python wheel,
   the single `runtime` extra, compatibility, and migration from v0.2.0/former extras.
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

## User stories

- As a new adopter, I can install both product surfaces and validate a project without
  mutating Snowflake.
- As a platform owner, I can identify each privilege and explicit apply/spend boundary
  before granting access or running automation.
- As an automation author, I can rely on documented commands, outputs, and exit codes that
  are checked against the shipped parser.
- As an upgrader, I can move from v0.2.0 without retaining copied tooling or retired extras.

## Dependencies

- REQ-002 v0.3.0 identity and Python ownership.
- REQ-003 explicit bootstrap configuration.
- REQ-004 lifecycle and safety hardening.
- REQ-005 dbt-rendered evaluation execution plan.
- REQ-006 stable domain-oriented CLI.

## Out of scope

- New CLI commands, macros, Agent/eval semantics, or Snowflake objects.
- Agent commit, alias movement, live mutation, runtime invocation, or paid evaluation.
- Public release, repository publication, or maintainer-policy changes.

## Notes

- Objective lever: replace repository-history documentation with an adopter journey whose
  examples are generated from or tested against the released parser and manifest contracts.
- Data proof: the argparse tree, package metadata, macro signatures, integration manifest,
  and existing lifecycle/eval tests provide local sources for every documented contract.
- Assembly line: install -> configure -> doctor/manifest validate -> render/plan -> explicit
  sandbox apply -> optional native evaluation -> local gate/baseline evidence.
- Reversible local choice: keep focused pages under the existing `docs/` hierarchy and add
  quickstart, configuration-model, and CLI reference pages rather than a new docs framework.
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
