# REQ-012: guided Cortex Code adoption skill

## Summary

Ship one canonical, script-free project skill that guides Cortex Code through adopting
`dbt_cortex_agent` 0.3.1 in a new or existing dbt project without creating a second Agent
lifecycle implementation.

## Business context

The package now has a deterministic Orders starter, manifest-owned Agent and evaluation
contracts, projection-aware previews, and guarded mutation/runtime/spend commands. Adopters
still need to assemble those surfaces into a safe sequence and distinguish project discovery,
local authoring, Snowflake mutation, paid evaluation, and baseline policy. A project skill can
make the supported path discoverable while keeping dbt Core and the shipped CLI authoritative.

## Objective

An adopter can move from an understood dbt project and a stated business outcome to a reviewed,
dbt-owned Cortex Agent definition and offline proof, then make each local-write, Snowflake,
evaluation-spend, and baseline-policy decision deliberately.

## Acceptance criteria

1. `.cortex/skills/dbt-cortex-agent-project/SKILL.md` is the only implementation artifact for
   the project skill, contains no scripts or copied lifecycle logic, and remains under 500 lines.
2. The skill starts with read-only project discovery and the Drivetrain sequence: objective,
   controllable levers, available data, proof criteria, and the assembly line from metadata to
   deployed and evaluated behavior.
3. The workflow supports four explicit routes: adopt an existing semantic view, use the fixed
   Orders starter, migrate an existing Agent definition into a dbt exposure, and optionally
   author a manifest-owned evaluation suite.
4. The skill uses only stable 0.3.1 package commands and metadata contracts. It runs normal fresh
   parse behavior, contains no `--no-parse`, invents no sandbox/database/name default, and treats
   dbt Core with `dbt-snowflake` as authoritative while describing Fusion/fdbt as advisory.
5. Cortex Code is the primary guided surface. Every executable package step also shows manual
   terminal command parity without requiring a generated wrapper, lifecycle script, or article.
6. The skill has mandatory, explicit stops before: writing or modifying local project files;
   applying any Snowflake mutation/runtime invocation; starting a paid evaluation; and accepting,
   overwriting, migrating, or otherwise moving a baseline.
7. Before each stop, the skill presents the objective, planned scope, exact commands/files, proof
   to review, and the resume condition. Preview commands never imply approval for a later boundary.
8. Structural, safety, shipped-parser, and deterministic trigger-corpus tests cover the skill.
   Positive prompts select it; adjacent dbt/Agent questions are near misses; unrelated prompts do
   not select it under the documented lexical contract.
9. README, adopter documentation, compatibility guidance, and changelog identify the project
   skill, its 0.3.1 authority, and its non-mutating default path without claiming publication,
   installation outside this repository, or live verification.
10. Verification runs focused and full Python tests, package build, wheel inventory, offline
    integration dependency/parse proof, and supported non-mutating starter/render/deploy/eval
    previews. It does not call Snowflake, invoke an Agent, spend credits, move a baseline, commit,
    push, or implement an article.
11. Doctor accepts an immutable full Git SHA when the installed dbt package metadata matches the
    companion CLI version; semantic version pins still require an exact direct match.

## User stories

- As a new adopter, I can use Cortex Code to choose between my semantic view and the fixed Orders
  starter, and I can review the same commands manually before any file is written.
- As an existing Agent owner, I can translate an Agent definition into dbt-owned exposure metadata
  and prove the rendered result without adding a parallel lifecycle script.
- As an evaluation author, I can add ground truth optionally and see separate approvals for paid
  execution and baseline movement.
- As a platform or cost owner, I can verify that target, database, connection, mutation, runtime,
  spend, and baseline choices are never inferred or crossed implicitly.

## Dependencies

- REQ-002 dbt/Python ownership boundary.
- REQ-003 explicit bootstrap configuration.
- REQ-004 lifecycle safety and fresh-manifest behavior.
- REQ-005 dbt-rendered evaluation plans and baseline policy.
- REQ-006 stable CLI process contract.
- REQ-007 adopter documentation.
- REQ-008 credential-free package verification.
- REQ-011 deterministic Orders starter and projection-aware previews.

## Out of scope

- Publishing or installing the project skill in a catalog or user-global skill directory.
- A generic Agent wizard, arbitrary semantic-model generation, or an article/tutorial post.
- New CLI commands, macros, lifecycle clients, wrapper scripts, or duplicated Agent DDL.
- Snowflake mutation, Agent invocation, paid evaluation, baseline movement, commit, or push.
- Treating Fusion/fdbt output as release authority.

## Notes

- Objective lever: sequence existing package contracts behind explicit human approvals rather than
  add another implementation layer.
- Data proof: REQ-011 already provides the fixed Orders fixture, canonical/native-eval rendering,
  deploy preview, general smoke preview, and eval-plan preview; existing metadata references define
  the exposure and ground-truth shapes.
- Assembly line: discover project -> state objective/levers/data/proof -> select route -> approve
  local authoring -> parse/validate/render/preview -> approve Snowflake mutation if requested ->
  approve paid evaluation if requested -> approve baseline policy separately.
- Reversible local choice: the skill uses lexical trigger-corpus tests as deterministic structural
  evidence; runtime skill selection remains a Cortex Code behavior outside this offline package.
- Critic: review only for mismatch against these criteria, especially accidental writes, inferred
  environments, unsupported commands, authority drift, and collapsed approval boundaries.
- Verifier: full offline package and integration proof is mandatory because command examples and
  project behavior are affected; no live substitute is permitted or needed.
- Adopter verification decision: a 40-character Git SHA identifies immutable source rather than a
  semantic package version, so doctor proves its version through the installed dbt package metadata.
