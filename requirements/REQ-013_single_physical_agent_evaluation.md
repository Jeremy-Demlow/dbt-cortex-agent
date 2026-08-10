# REQ-013: single physical Agent evaluation

## Status

Complete. Tasks 3-5 established the single-Agent lifecycle, evaluation identity,
and capability semantics. Task 6 starter, project-skill, and active-documentation
migration completed with offline verification.

## Summary

For each enabled Agent exposure in a resolved dbt target, deploy exactly one physical Cortex Agent
and, when evaluation metadata is present, evaluate that same Agent. Evaluation metadata is optional
configuration for proof, not a second deployment projection or Agent lifecycle.

## Business context

REQ-005, REQ-011, and REQ-012 established useful historical behavior around a separate
`native_eval` projection and physical evaluation Agent. Direct Snowflake probes now show that native
Agent Evaluations can complete against Agents with substantial attached capabilities. Maintaining a
second suffixed Agent creates identity drift, duplicates lifecycle state, and makes evaluation
history for a different object look like evidence for the enabled exposure's deployed Agent.

## Objective

An operator can deploy an enabled exposure normally and optionally evaluate the resulting physical
Agent, with one FQN and one lifecycle per exposure and target, so evaluation evidence describes the
same object users invoke.

## Acceptance criteria

1. An enabled Agent exposure with no evaluation metadata validates, renders, and deploys normally;
   evaluation metadata is not required for Agent deployment or lifecycle operations.
2. Evaluation metadata is optional and, when present, identifies suites, datasets, metrics, and
   proof policy for the physical Agent already selected by the enabled exposure and resolved target.
3. For one enabled exposure in one resolved target, deploy and evaluation resolve exactly one
   physical Agent FQN. The evaluation plan and result evidence record that same FQN.
4. Evaluation never creates, deploys, clones, suffixes, replaces, or otherwise mutates an Agent.
   Evaluation requires the one physical Agent to exist and fails closed if its identity cannot be
   proven from manifest-owned metadata and resolved target context.
5. Agent deployment is independent of evaluation metadata and never selects an evaluation-specific
   specification. Adding, changing, disabling, or removing evaluation metadata cannot alter the
   deployed Agent specification or trigger Agent lifecycle work.
6. The supported contract has no physical canonical/native-eval projection split. The projection
   assumptions recorded in REQ-005, REQ-011, and REQ-012 remain historical facts but are explicitly
   superseded by this requirement for future implementation and baseline decisions.
7. Capability proof is classified per capability as: `attached` when the deployed specification
   contains it; `invoked` only when trace or metric evidence proves a call; `completed_with_attachment`
   when an evaluation completed while it was attached but no call is proven; `absent` when the
   deployed specification omits it; or `indeterminate` when available evidence cannot establish
   attachment or invocation. Completion alone must not be reported as invocation proof.
8. Historical `_EVAL` Agent runs and artifacts remain auditable migration evidence, but they are
   superseded histories rather than candidate or accepted baselines for the single-FQN contract.
   Baselines for this requirement must identify the same physical Agent FQN as the enabled exposure.
9. Public Agent render, deploy, smoke, grant, version, and alias interfaces expose no projection
   selector. They resolve one physical target, render the full specification, and preserve mutation
   guards, staged-skill validation/upload, MCP attachment, versioning, aliases, and grants.
10. Render artifacts use the stable non-projection path
    `renders/<target>/<agent>/spec.json`; the render envelope carries a `single_agent` lifecycle
    marker and no projection identity.
11. Evaluation plans, candidates, results, and baselines carry no projection field. Their signed
    identity includes the one target-resolved Agent FQN, and schema-v2 artifacts retain plan
    signature, policy, ordered refs, and pre/post version provenance.
12. Before START, evaluation proves that the target Agent exists and has a DEFAULT version. It
    records that version, uses the same FQN in generated config, status, results, and logs, and
    fails closed when DEFAULT changes before completion. No evaluation path invokes an Agent
    lifecycle macro.
13. Legacy baseline migration rejects `_EVAL` physical identity as incompatible with this
    requirement unless an explicit future historical-only workflow is introduced. It never
    silently promotes that evidence into a current single-Agent baseline.
14. This task changes focused evaluation metadata, execution-plan macros, Python clients,
    schema-v2 artifacts, starter/integration metadata only where required, tests, focused
    evaluation docs, requirement notes, and regression evidence. It runs no Snowflake command,
    deployment, evaluation, consumer edit, commit, or push.
15. Package capability evidence uses one general structure whose classification is exactly one of
    `attached`, `invoked`, `completed_with_attachment`, `absent`, or `indeterminate`. Offline
    metadata/render inspection may prove attachment or absence; only supplied trace/metric evidence
    may prove invocation, and only supplied completed-run evidence may prove completion with an
    attachment.
16. Native Agent evaluation `expected_tools` may name only declared Analyst, Cortex Search,
    `web_search`, or generic custom tools. Validation rejects skill, MCP, `code_execution`, and
    other rendered capability names as native-coverage claims, and rejects undeclared names.
17. Generic custom tools are validated by declared tool type and name at package level. Therefore
    a declared generic tool such as `StaffingSimulator` is eligible for native tool ground truth,
    but this task does not change a consumer dataset or claim that the current dataset invokes it.
18. `evaluation_supported` is not a render/deploy selector. Removed declarations have no effect on
    Agent identity or specification; any temporarily retained occurrence is documentary proof
    metadata only and cannot filter a tool, capability, skill, or MCP connector from deployment.
19. The Orders starter and integration fixture contain one unsuffixed Agent exposure. Their optional
    eval model uses a descriptive suite model name without a physical-Agent `_EVAL` convention, and
    removing that optional model leaves the Agent-only adoption path valid and documented.
20. The project-local Cortex Code skill treats evaluation authoring as optional, shows manual parity
    for one Agent, and never proposes a second Agent or a `native_eval` deployment. Its four approval
    boundaries remain unchanged.
21. Active package and integration documentation consistently describes one physical Agent plus an
    optional eval model. Active CLI/macro/variable/metadata examples match shipped interfaces and no
    page claims that version 0.3.1 is currently available from PyPI.
22. Historical requirement, regression, and release-history references may retain old projection or
    `_EVAL` terminology only when the text explicitly identifies it as superseded history.

## User stories

- As an Agent owner, I deploy one physical Agent for an enabled exposure and can omit evaluations
  without changing the deployment path.
- As an evaluation author, I attach optional proof metadata to the same physical Agent that users
  invoke, without creating an evaluation-only Agent.
- As an operator, I can trace deploy, runtime, evaluation, version, alias, and baseline evidence to
  one physical Agent FQN per exposure and target.
- As a reviewer, I can distinguish an attached capability from a capability proven to have been
  invoked and can see when evidence is absent or indeterminate.
- As a baseline owner, I do not treat historical suffixed `_EVAL` Agent evidence as the baseline for
  the single-FQN contract.
- As a new adopter, I can stop after defining and proving one Agent; evaluation files and paid proof
  are optional additions rather than deployment prerequisites.

## Dependencies

- REQ-002 dbt/Python ownership boundary.
- REQ-004 lifecycle safety and manifest-owned identity.
- REQ-005 dbt-rendered evaluation plan and evidence policy, except where superseded here.
- REQ-011 projection-aware historical behavior, except where superseded here.
- REQ-012 guided optional evaluation authoring, except where superseded here.

## Out of scope

- Broad Agent lifecycle, consumer, skill, or unrelated documentation migration.
- Migrating, deleting, renaming, or deploying any existing Snowflake Agent.
- Running Snowflake probes, Agent Evaluations, smoke tests, or paid Cortex operations in this slice.
- Introducing a historical-only `_EVAL` migration opt-in.
- Claiming that an attached capability was invoked without trace or metric evidence.

## Notes

- Objective lever: remove evaluation-specific physical identity and make optional evaluation metadata
  reference the exposure's one resolved deployment identity.
- Data proof supplied for this requirement: `RESORT_EXECUTIVE_DBT_FOCUS` completed 7 records with
  zero errors and two attached skills. This is `completed_with_attachment` proof for the skills, not
  proof that either skill was invoked on every record.
- Data proof supplied for this requirement: `SKI_OPS_ASSISTANT_DBT_FOCUS` completed 16 records with
  zero errors or warnings while skills, Cortex Search, web search, data-to-chart, and
  `StaffingSimulator` were attached. Each attachment has `completed_with_attachment` proof unless
  separate trace or metric evidence establishes `invoked`.
- The currently deployed `SKI_OPS_ASSISTANT_DBT_FOCUS` specification did not include
  `code_execution`, so its classification is `absent`, not failed or unsupported.
- MCP attachment is `indeterminate` from the supplied probe. Current documentation says evaluation
  runs with MCP attached but MCP is not called; that statement is not invocation proof.
- These direct probe observations were provided as requirement evidence. This requirements-only
  slice does not reconnect to Snowflake or reproduce the paid runs.
- Assembly line for the future implementation slice: exposure metadata -> one target-resolved Agent
  FQN -> normal deploy/version lifecycle -> optional eval-plan render for that FQN -> capability
  proof classification -> evaluation evidence and same-FQN baseline gate.
- Supersession is prospective. REQ-005, REQ-011, and REQ-012 continue to describe what earlier
  releases implemented and verified; their physical projection assumptions are not future baselines.
- Critic record (2026-08-10): requirement-only review must reject any language that equates
  attachment with invocation, lets evaluation mutate Agent lifecycle, or promotes `_EVAL` history to
  the new baseline.
- Critic outcome (2026-08-10): no blocking requirement mismatch remains. The contract keeps
  evaluation metadata optional, binds deploy and evaluation to one FQN, classifies completion with
  attachments separately from invocation, and preserves `_EVAL` evidence only as superseded history.
- Verifier: substituted by focused requirement and documentation contract tests because this slice
  changes no SQL, macro, model, eval execution, deploy behavior, or product code.
- Verifier record (2026-08-10): 33 focused requirement/documentation tests passed and
  `git diff --check` passed. No macro, CLI behavior, dbt execution, Snowflake call, deployment,
  evaluation, consumer edit, commit, or push ran.
- Task 3 implementation note (2026-08-10): removed projection arguments from public Agent macros
  and CLI commands; removed `_EVAL` suffix generation and the `cortex_agent_eval_suffix` variable;
  full specification rendering, skill upload/readiness/hash behavior, MCP DDL, mutation guards,
  grants, versions, and aliases now target the exposure's single resolved Agent FQN.
- Transitional eval compatibility (2026-08-10): eval metadata is not an Agent deploy input. Eval
  macros resolve the same unsuffixed Agent FQN and emit `projection: single_agent` only as a fixed
  schema-v1 compatibility marker; this task does not redesign eval artifacts or metadata broadly.
- Task 4 objective (2026-08-10): evaluation evidence for an optional suite is generated against the
  already deployed normal Agent FQN, with no projection metadata, no lifecycle call, and one stable
  DEFAULT version from pre-START proof through result collection.
- Task 4 acceptance proof is focused on plan/config/artifact identity, Agent existence/version
  validation, lifecycle-call absence, `_EVAL` migration rejection, version-drift failure, and
  artifact-backed documentation contracts. Artifact schema remains v2 because removing the obsolete
  projection field tightens an existing optional identity representation rather than changing the
  evidence model or reader compatibility boundary.
- Task 4 maker record (2026-08-10): removed projection from eval metadata, signed plan identity,
  `EvalPlan`, native result metadata, candidates, and baselines; retained datasets, paid apply,
  allowlists, polling/retry, thresholds/tolerances, and schema-v2 evidence; added pre-upload and
  pre-START Agent DEFAULT proof using the same normal FQN throughout.
- Task 4 critic record (2026-08-10): identified three blocking gaps in the first pass: artifacts
  persisted only a partial plan identity, supplied projection metadata was ignored rather than
  rejected, and native config Agent identity was not cross-checked against the signed FQN. The fix
  persists and validates complete signed identity, rejects projection metadata/plan fields, and
  requires native config identity equality. No blocking finding remains against the acceptance
  criteria.
- Task 4 verifier record (2026-08-10): 180 focused eval, baseline, CLI, deploy, macro, requirement,
  and artifact-linked documentation tests passed; credential-free dbt Core 1.11.11/dbt-snowflake
  1.11.4 parsed the integration consumer with partial parsing disabled; `git diff --check` passed.
  No connector-backed Snowflake operation, deployment, paid evaluation, consumer edit, commit, or
  push ran.
- Task 5 objective (2026-08-10): make capability proof precise enough that package validation can
  distinguish declared/attached capability evidence from native-evaluation invocation coverage,
  without changing the single Agent's rendered specification, identity, or deploy lifecycle.
- Task 5 levers and data: derive offline attachment/absence evidence from manifest-owned Agent
  metadata plus the full rendered specification; validate eval `expected_tools` against the native
  supported declared tool classes; preserve the supplied canonical 7-record and 16-record probes
  as completed-with-attachment evidence; require external trace/metric evidence for invocation.
- Task 5 acceptance proof is focused on the five-value evidence vocabulary, deterministic generic
  evidence structure, allowed Analyst/Search/web/custom expected-tool resolution, fail-closed
  skill/MCP/code-execution coverage claims, removal of obsolete `evaluation_supported` declarations,
  render identity/spec invariance, and offline parse. `StaffingSimulator` is package-level generic
  tool coverage only; no consumer dataset is edited.
- Task 5 critic record (2026-08-10): the first pass allowed an unsupported capability declaration
  to shadow a declared native-supported tool with the same name and did not validate the
  `expected_tools` container/entries. The fix gives declared Analyst/Search/web/generic tools
  precedence and rejects non-list, empty, or non-string expected-tool metadata. No blocking
  requirement mismatch remains.
- Task 5 verifier record (2026-08-10): 132 focused capability, eval, render/deploy, requirement,
  and artifact-linked documentation tests passed. dbt Core 1.11.11/dbt-snowflake 1.11.4 resolved
  local integration dependencies, parsed the consumer with partial parsing disabled, and rendered
  offline capability evidence for the Orders Agent as one attached Analyst tool with skills,
  code execution, and MCP absent. `git diff --check` passed. No Snowflake connection, deployment,
  paid evaluation, consumer edit, commit, or push ran.
- Task 6 objective (2026-08-10): an adopter sees one physical Agent throughout starter generation,
  guided adoption, lifecycle, evaluation, and reference documentation, and can choose an Agent-only
  path without creating or deploying evaluation resources.
- Task 6 levers and data: update the packaged Orders fixture and its exact integration mirror; keep
  optional suite metadata bound to `orders_assistant`; remove obsolete projection options and
  `_EVAL` prerequisites from active docs and project-skill commands; preserve historical requirement
  and regression evidence as explicitly superseded text.
- Task 6 acceptance proof covers starter/init determinism, agent-only and Agent-plus-eval examples,
  project-skill command parsing and approval boundaries, active-document terminology, offline dbt
  parse, package build/Twine/wheel inventory, focused/full tests where feasible, and repository hooks.
  It performs no Snowflake operation, consumer deployment, paid evaluation, commit, or push.
- Task 6 critic record (2026-08-10): the first pass found active projection commands in the project
  skill and references, an eval-prefixed Orders model, stale `_EVAL` prerequisites, and PyPI install
  commands that could be read as currently available. The fix removed those active contracts,
  renamed the optional suite model to `orders_assistant_core`, retained only explicit historical or
  rejection references, and kept all four approval stops unchanged. No blocking finding remains.
- Task 6 verifier record (2026-08-10): 186 focused docs/project-skill/starter/init/CLI tests and the
  complete 306-test package suite passed; dbt Core 1.11.11/dbt-snowflake 1.11.4 completed an offline
  integration parse with placeholder profile values; sdist/wheel build, Twine metadata checks,
  exact wheel inventory, and `git diff --check` passed. Repository hook coverage is represented by
  the available checked-in test/build guards because this repository has no pre-commit config.
  No Snowflake operation, paid evaluation, consumer deployment, commit, or push ran.
- Independent candidate review (2026-08-10): empty `DESCRIBE AGENT` results now fail as missing
  Agent evidence before stage upload or evaluation START. This closes the remaining fail-closed
  existence-proof edge case without changing the signed plan, schema-v2 artifact, or lifecycle
  boundary.
- Independent verifier record (2026-08-10): 320 tests passed on Python 3.10, 3.11, and 3.13;
  dbt Core 1.11.11/dbt-snowflake 1.11.4 completed credential-free dependency resolution and
  offline parse. `dbt compile` was attempted but requires a Snowflake connection for the semantic
  view materialization and therefore was not used as an offline gate. Installed-wheel verification
  passed on dbt 1.10/1.11 without Snowflake, runtime invocation, or paid evaluation.
