# REQ-011: additive v0.3.1 tutorial product readiness

## Summary

Make the v0.3.1 adopter path complete and reproducible by correcting tutorial defects, shipping one
deterministic Orders starter, exposing projection-aware Agent render/deploy behavior, and adding a
general Agent smoke boundary without breaking v0.3.0 consumers.

## Business context

The v0.3.0 package proves the underlying dbt metadata, lifecycle, evaluation, and release contracts,
but the first-use path is still assembled from documentation examples and an integration fixture.
The CLI also fixes Agent render/deploy to the canonical projection, while live smoke is coupled to
skills. An adopter needs one supported tutorial path that can be reproduced locally, can explicitly
select either supported projection, and can smoke any deployed Agent without implying that a skill
is required. Product-readiness work must remain additive and retain the existing explicit mutation,
runtime, and spend boundaries.

## Objective

A new adopter can reproduce the curated Orders tutorial from package-owned inputs, preview the exact
Agent projection that would be deployed, and deliberately smoke the corresponding deployed Agent,
while an existing v0.3.0 consumer continues to receive canonical, non-mutating behavior by default.

## Acceptance criteria

1. Documentation defects are corrected across README, installation, quickstart, first-Agent,
   lifecycle, CLI reference, compatibility, troubleshooting, and integration-consumer guidance:
   commands parse with the shipped CLI; names and paths agree with package-owned artifacts; v0.3.1
   release identity is consistent; projection and smoke behavior are explicit; and no page claims
   that preview, smoke, deployment, or evaluation performs work outside its documented boundary.
2. The package exposes one curated, deterministic Orders starter backed by synthetic data. Given the
   same package version and explicit inputs, repeated creation produces the same tracked project
   content and manifest-owned Agent/eval metadata, preserves existing files unless an explicit
   overwrite is requested, and requires no Snowflake connection for creation, parse, validation,
   canonical render, native-eval render, or deploy preview.
3. The Orders starter is a fixed tutorial product, not a generic project or Agent wizard. v0.3.1 does
   not solicit arbitrary domains, infer schemas or business semantics, generate open-ended Agent
   instructions, or introduce a reusable templating framework for custom starters.
4. Public Agent render and deploy entry points accept an explicit `canonical` or `native_eval`
   projection and pass that exact value to the existing dbt macros. Omitting projection preserves
   v0.3.0 canonical render/deploy behavior. Help, JSON output, dry-run text, and documentation identify
   the selected projection and physical target without deriving either from remote Snowflake state.
5. A general Agent smoke command can preview or invoke any selected manifest-owned Agent projection,
   including an Agent with no skills. Preview resolves and reports the logical Agent, projection,
   physical Agent, request, and safety context without connecting. Applied smoke requires the runtime
   extra, explicit connection, matching dbt-resolved database, target/database allowlists, and an
   explicit apply flag; it returns stable human/JSON results and controlled exit codes.
6. v0.3.0 metadata and command invocations remain valid. Existing Agent exposure and eval contracts,
   macro defaults, package names, lifecycle/versioning semantics, artifact schemas, and canonical
   output remain unchanged unless the caller opts into a new v0.3.1 surface. The existing skill smoke
   command remains supported and retains its skill-selection assertions.
7. Starter creation, render, deploy, and general Agent smoke are non-mutating by default. No command
   implicitly connects, uploads, creates or alters a Snowflake object, commits a version, moves an
   alias, grants access, invokes an Agent, starts an evaluation, accepts a baseline, or incurs Cortex
   spend. Every mutation, runtime invocation, or paid action remains separately labeled and requires
   explicit operator opt-in.
8. The package completion gate requires version-aligned package metadata and docs; deterministic
   starter regeneration and clean-checkout proof; parser/docs/policy contracts; focused projection,
   deploy-preview, smoke-preview, and backward-compatibility tests; the full Python suite; supported
   dbt dependency resolution and offline parse; canonical and native-eval render parity; package
   build, Twine, wheel inventory, and clean installed-wheel smoke; and no generated residue. The gate
   must pass without credentials, Snowflake calls, live runtime invocation, mutation, or paid eval.
9. A companion Cortex Code/catalog skill for the tutorial is deferred until the package completion
   gate in criterion 8 passes. v0.3.1 package readiness must not depend on that skill, and this slice
   does not create, publish, install, or document the skill as available.
10. Requirements, user stories, test cases, and focused docs/policy contracts capture criteria 1-9
    before product implementation begins.

## User stories

- As a new adopter, I can create the same synthetic Orders starter every time and prove both Agent
  projections locally before deciding whether to connect to Snowflake.
- As an Agent operator, I can explicitly render, preview deployment, and smoke the projection I intend
  to operate without requiring the Agent to have a skill.
- As an existing v0.3.0 consumer, I retain canonical defaults and current metadata, lifecycle,
  evaluation, and skill-smoke behavior until I opt into an additive v0.3.1 surface.
- As a security or cost reviewer, I can prove that starter, render, deploy preview, and smoke preview
  do not connect, mutate state, invoke a runtime, or spend credits implicitly.
- As a release operator, I can block tutorial-skill work until the package itself passes one complete,
  credential-free product gate.

## Dependencies

- REQ-002 v0.3.0 identity and Python ownership.
- REQ-003 explicit bootstrap configuration.
- REQ-004 lifecycle and safety hardening.
- REQ-006 stable domain-oriented CLI.
- REQ-007 complete adopter documentation.
- REQ-008 standalone CI and release verification.
- REQ-010 trusted PyPI publishing.

## Out of scope

- Implementing the package completion gate in this general Agent smoke slice.
- A generic wizard, arbitrary-domain scaffolding, prompt generation, or a starter plugin framework.
- Creating or changing semantic business logic beyond the fixed synthetic Orders tutorial.
- Removing or repurposing skill plan, upload, or smoke behavior.
- Creating, publishing, installing, or distributing a Cortex Code/catalog skill.
- Calling Snowflake; deploying or invoking an Agent; uploading a skill; accepting a baseline;
  running a paid evaluation; publishing a package; committing; or pushing.

## Notes

- Objective lever: turn the existing package-owned Orders fixture and projection macros into one
  explicit adopter contract, then separate general Agent runtime proof from skill-specific proof.
- Data proof: the repository already contains synthetic Orders seed data, one semantic view, one
  Agent exposure, one eval suite, deterministic canonical/native-eval macros, dry-run deployment,
  and skill-specific smoke. Product implementation must reuse those authorities rather than create
  parallel metadata or lifecycle paths.
- Assembly line: requirements contract -> deterministic Orders starter -> projection-aware local
  render/deploy preview -> general Agent smoke preview -> backward-compatibility proof -> package
  completion gate -> optional skill work in a later requirement.
- Reversible local choice: `canonical` remains the omitted render/deploy default; `native_eval` is an
  explicit projection, not an inferred evaluation mode.
- Reversible local choice: general Agent smoke is additive; skill smoke remains the stronger check
  for server-side skill selection.
- Deterministic Orders starter slice objective: an adopter can preview and apply one package-owned
  Orders fixture to an existing dbt project without a connection or partial writes.
- Deterministic Orders starter slice acceptance: `init --starter orders` reports every planned path
  and action in human and JSON output; writes the fixed seed, semantic view, Agent exposure, and eval
  files only with `--apply`; appends the starter skill exclusion to `.dbtignore`; adds the pinned
  `Snowflake-Labs/dbt_semantic_view` dependency when absent; preserves an existing semantic-view
  dependency; validates every collision before any write; leaves byte-identical files unchanged; and
  fails closed for every differing existing file. No force or generic wizard surface is introduced.
- Reversible local choice: the starter extends the existing `init` command and its explicit package
  source/safety configuration rather than creating a second project-initialization path.
- Verifier: this starter slice requires focused and full Python tests, package build and exact wheel
  inventory, clean installed-wheel starter smoke, offline dependency/parse proof when locally
  feasible, and pre-commit. Snowflake calls remain prohibited.
- Projection/render/deploy slice objective: an operator can select `canonical` or `native_eval`,
  inspect the exact dbt-rendered specification as structured CLI output and a deterministic local
  artifact, and deploy that same projection through the existing guarded lifecycle path.
- Projection/render/deploy slice acceptance: render and deploy default to `canonical`, reject every
  other projection in both CLI and macros, pass the selected value unchanged, identify the logical
  and physical Agent, parse exactly one marked JSON object from dbt output, fail closed for a
  missing, duplicate, malformed, or non-object marker, and write
  `target/dbt_cortex_agent/renders/<target>/<agent>/<projection>.json`. Native-eval deploy retains
  fresh-manifest, explicit connection, resolved-database, target/database allowlist, and macro
  mutation guards while skipping canonical-only local skill planning and upload. Canonical deploy
  orchestration remains unchanged.
- Reversible local choice: the marked render payload is emitted by the dbt macro because dbt owns
  physical naming and specification construction; Python only validates the transport envelope and
  writes the contained deterministic artifact.
- Critic: adversarial review is required for projection validation coverage, marker ambiguity,
  artifact containment, canonical compatibility, native-eval safety gates, and accidental skill
  orchestration.
- Verifier: this slice requires focused and full Python tests, macro/integration dependency and
  parse proof, package build and wheel inventory, and pre-commit. Snowflake calls remain prohibited.
- General Agent smoke slice objective: an operator can preview and deliberately invoke one
  manifest-owned Agent without requiring a skill declaration or introducing another Agent HTTP
  client.
- General Agent smoke slice acceptance: `agent smoke` requires exactly one nonblank logical
  `--agent` and nonblank `--question`; accepts optional `--expect-tool`, `--agent-object`, and
  `--endpoint`; resolves the physical Agent from manifest target naming unless explicitly
  overridden; and emits stable `command`, `applied`, `agent`, `agent_object`, `question`,
  `expected_tool`, `passed`, and `response` fields. Preview never constructs a connector or invokes
  an Agent and returns null `passed` and `response`. Apply requires a fresh manifest, explicit
  connection, database/schema, matching manifest database, and CLI target/database allowlists
  before reusing `invoke_agent`; an expected tool must exactly match a returned tool-use name.
  Configuration, runtime, HTTP/SSE, and assertion failures remain controlled exit 2 failures.
- Reversible local choice: general Agent smoke selects one logical Agent rather than inheriting the
  repeatable multi-Agent lifecycle selector; one question maps to one invocation and one result.
- Reversible local choice: general Agent smoke defaults to the v0.3.0 canonical physical identity,
  while explicit `native_eval` smoke resolves its physical object through the existing offline dbt
  render authority. Python must not guess the configurable native-eval suffix.
- Critic: adversarial review is required for blank inputs, preview side effects, physical override
  validation, pre-connector gate ordering, exact tool assertions, JSON shape, controlled failures,
  and any change to existing skill smoke.
- Verifier: this slice requires focused/full Python tests, byte compilation, package build, Twine,
  wheel inventory, installed-wheel CLI smoke, and offline integration-consumer dbt parse. Live Agent
  or Snowflake calls are prohibited.
