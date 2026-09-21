---
name: dbt-cortex-agent-project
description: "Guide creation, deployment, versioning, retirement, or evaluation of a dbt-owned Snowflake Cortex Agent with dbt_cortex_agent. Use for a generic Agent, optional Semantic View, Orders starter, existing Agent migration, lifecycle operation, or manifest-owned evaluation."
---

# dbt Cortex Agent project adoption

Guide one project from evidence to a dbt-owned Agent. Cortex Code performs discovery,
edits, and verification; every executable package step also shows the exact manual
command. This skill is guidance only: do not create wrapper scripts or duplicate Agent
lifecycle logic.

## Authority and invariants

- This workflow targets `0.0.9`. Detect the installed `dbt-cortex-agent` version
  and require Python and dbt to identify the same immutable release. If they differ
  or another version is installed, stop and review that version's documentation;
  do not silently upgrade or apply this workflow to historical contracts.
- Define each Agent as a dbt model with `materialized='cortex_agent'`; dbt compile
  renders it and the `agent deploy` workflow invokes dbt build as the only Agent
  deployment authority.
- dbt Core with `dbt-snowflake` is authoritative for parse, graph, manifest, and release
  proof. Fusion/fdbt may provide advisory feedback but never replaces dbt Core evidence.
- dbt owns Agent/eval definitions, rendering, resolved physical naming, lifecycle macros,
  versions, aliases, and eval plans. One enabled Agent model resolves one physical Agent;
  optional evaluation targets that same Agent. The CLI coordinates those contracts.
- Infrastructure and grants are adopter-owned. Do not invent an Agent grant macro or
  assume metadata grants access. CoWork visibility and consumer-role verification are
  separate infrastructure/consumer operations, not additional Agent deployments.
- Let manifest-dependent commands run their normal fresh parse. Never bypass parsing.
- Discover target, database, schemas, connection, warehouse, role, Agent names, semantic
  views, and safety allowlists from the project and user. Do not invent environment values.
- Preview is evidence, not approval for a later write, mutation, runtime, spend, or policy
  boundary.
- An Agent does not require a Semantic View. Treat Analyst, Search, skills, MCP,
  evaluation, and experimental configuration as optional capabilities. Preserve
  experimental mappings, but do not invent private-preview-specific scaffold options.
- Load the checked-out release's `docs/reference/agent-metadata.md`,
  `docs/guides/lifecycle.md`, and capability-specific guides before authoring.
  These paths are relative to the package repository root, not the consumer project.
  If unavailable locally, obtain matching release documentation rather than guessing.

## Workflow

### 1. Discover the project read-only

Use Cortex Code file and search tools to inspect, without editing:

1. Repository instructions and contribution rules.
2. `dbt_project.yml`, dependency declarations, profile/target conventions, and dbt version.
3. Semantic-view models, Agent models, eval models, tests, and generated manifest if present.
4. Existing Agent definitions or exported specifications supplied by the user.
5. Current Git status so unrelated work is preserved.

Run only read-only local checks as needed, such as `dbt --version` and CLI help. Do not run
`dbt deps` yet if it would write dependency artifacts.

Report discovered facts, unknowns, and whether the project is new or established. If no dbt
project exists, explain that the package configures an existing dbt project; establish the dbt
project separately before continuing.

### 2. Establish the Drivetrain contract

Before choosing files or commands, state and confirm:

- **Objective:** the change in user or business behavior the Agent should produce. Do not use
  a metric or implementation action as the objective.
- **Levers:** semantic views, Agent instructions/tools, governed data, evaluation questions,
  deployment target, and access policy the project can control. Identify the lever expected to
  move the objective.
- **Data:** relations, semantic views, representative questions, current Agent behavior, and
  ground truth available to prove feasibility. Record gaps instead of inventing semantics.
- **Proof:** offline parse/validation/render evidence first; optional runtime and evaluation
  evidence only behind later approvals.
- **Assembly line:** Agent metadata -> parse -> validate -> package deploy preview -> optional
  approved package deploy/runtime -> optional eval-model authoring and package verify preview ->
  approved paid verification -> separately approved baseline policy.

If objective, controllable lever, or supporting data is missing, stop with a concise gap report.

### 3. Select one adoption route

Choose from discovered evidence and user intent. Do not combine routes unless needed.

#### A. Generic Agent scaffold

Use when the user wants a new Agent and no governed data capability is required yet.
Preview before local writes:

```bash
dbt-cortex-agent agent scaffold --project-dir <PROJECT_DIR> --agent <AGENT> --json
```

Optionally add `--semantic-view-model <MODEL>` or `--with-eval`. Neither is required.

#### B. Existing semantic view

Use when a dbt semantic-view model already represents the governed domain.

Use the package scaffold, not an exposure or a second metadata specification:

```bash
dbt-cortex-agent agent scaffold --project-dir <PROJECT_DIR> --agent <AGENT> --semantic-view-model <MODEL> --json
```

After STOP 1, apply the same command with `--apply`. Keep its no-output `ref()`
dependency and rendered semantic-view FQN in native `tool_resources`. Put
instructions and tools in the model's YAML body. Derive physical identity from
the resolved model database/schema/alias, including dbt schema-generation rules.

#### C. Fixed Orders starter

Use only for the package-owned synthetic tutorial. It is not a generic wizard and must not be
adapted into inferred business semantics.

Preview package/dependency, safety-var, seed, semantic-view, Agent, eval, and `.dbtignore`
actions:

```bash
dbt-cortex-agent init --project-dir <PROJECT_DIR> --starter orders --package-source <PACKAGE_GIT_URL> --revision <PACKAGE_TAG> --target <TARGET> --allow-target <TARGET> --allow-database <DATABASE> --json
```

#### D. Existing Agent migration

Use when an Agent exists outside dbt. Read its provided definition and map it into one Agent model;
do not write a lifecycle importer or infer missing business meaning.

Create a migration table for review:

| Existing concern | dbt-owned destination |
|---|---|
| Instructions, models, orchestration | Native YAML body, including explicit `models.orchestration` |
| Analyst tool | Native `tools` and `tool_resources`, plus no-output `ref()` dependencies |
| Search/tools/experimental configuration | Preserve supported native YAML fields without lossy translation |
| Physical name | dbt model database/schema/alias; verify resolved FQN matches the migration plan |
| Display name/comment/deploy alias | Top-level `config.meta.agent_display_name`, `agent_comment`, `deploy_alias` |
| Usage roles | Reviewed adopter infrastructure; not Agent metadata |
| Skills | Native top-level `skills` plus matching `config.meta.cortex_agent.skills` for local upload planning |
| MCP | Preserve native configuration and separately verify external prerequisites and attachment behavior |
| Versions/aliases | Package lifecycle commands after separate approval; do not promise historical version import |

Flag unsupported or unavailable fields. Preserve the existing live Agent until dbt render and an
approved migration plan prove parity; never mutate it during discovery or authoring.
Compare rendered native YAML with the provided specification structurally. Explicitly
review profile, physical identity, tools, experimental fields, and intended changes.
For local skills, require matching name/source type/stage path in both declarations,
provisioned stages, and actual local files. Fresh parse does not render arbitrary Jinja
or reliably supply compiled bodies. Do not infer an empty upload plan means no skills.

#### E. Optional evaluation authoring

Add this route only when representative questions and ground truth exist. It is optional: an Agent
can be authored, rendered, deployed, and smoked without an eval model. Plan a table model with
`config.meta.cortex_eval`, stable question IDs/refs, metrics, thresholds, and regression tolerances.
The suite's `agent` field names the same enabled Agent model; never create, deploy, clone, or suffix a
second Agent for evaluation. Each row must emit one `OUTPUT` VARIANT. Use
`ground_truth_output` for answer correctness and `ground_truth_invocations` for tool metrics;
expected tool names must match declared native tool names exactly.

Skills and MCP behavior require separate smoke/integration proof because native Agent Evaluation
does not cover them.

#### F. Existing Agent lifecycle

For inspect/promote/rollback/retire requests, do not scaffold or author evaluation.
Load the lifecycle guide. Present a minimal STOP 1 packet for fresh-parse artifacts
and any dependency installation, then proceed to Step 6 after that approval.
No authoring/scaffold steps are needed, but parsing still writes local artifacts.
Confirm the desired version/alias or retirement objective rather than requiring new
business ground truth. Preserve all existing immutable versions during routing.

### 4. Present the local change plan

Show:

1. Objective, chosen route, and lever/data justification.
2. Exact files to create or modify and a concise diff outline.
3. Dependency and project-variable changes, preserving existing values.
4. Manual commands that will follow the write.
5. Acceptance evidence and unresolved assumptions.

Present one boundary packet containing the objective, exact local paths and changes, exact commands,
expected proof, risks, and the one-plan resume condition.

## STOP 1 — local project writes

Do not create, edit, generate, install dependencies, or apply starter files until the user
explicitly approves the listed local paths and changes. Use the structured question tool.

Resume only for the approved local file plan. If any path, change, or command changes, present the
revised packet and stop again.

### 5. Apply approved local changes

For route A, manual command parity is the reviewed preview plus `--apply`:

```bash
dbt-cortex-agent agent scaffold --project-dir <PROJECT_DIR> --agent <AGENT> --apply --json
```

For route C, manual command parity is the reviewed preview plus `--apply`:

```bash
dbt-cortex-agent init --project-dir <PROJECT_DIR> --starter orders --package-source <PACKAGE_GIT_URL> --revision <PACKAGE_TAG> --target <TARGET> --allow-target <TARGET> --allow-database <DATABASE> --apply --json
```

For route B, retain `--semantic-view-model <MODEL>` when adding `--apply` to its preview.
For routes D or E, use Cortex Code file tools to make only the approved metadata/model/test
changes. Do not generate scripts. Add the pinned package dependency and explicit safety vars only
when absent; preserve adopter configuration.

Then show manual local verification parity:

```bash
dbt deps --project-dir <PROJECT_DIR>
dbt parse --project-dir <PROJECT_DIR> --target <TARGET>
dbt-cortex-agent doctor --project-dir <PROJECT_DIR> --target <TARGET> --json
dbt-cortex-agent manifest validate --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --json
dbt compile --project-dir <PROJECT_DIR> --target <TARGET> --select <AGENT>
dbt-cortex-agent agent deploy --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --allow-target <TARGET> --allow-database <DATABASE> --json
```

Run the applicable commands through Cortex Code. The deploy command above is a preview: it does
not mutate Snowflake without `--apply`. Report parse, validation, rendered identities/specs, planned
mutation, and failures. Do not paper over dbt Core failures with advisory Fusion/fdbt output.
These commands can write local artifacts. Compile is non-mutating, not necessarily
offline: adapters/macros may connect or query. Review macros and approve credentialed
reads/compute before compile; do not run unknown effectful macros under a local-only
approval. Add discovered profile/connection context where required. Quote substituted
paths and values; use absolute project, candidate, and baseline paths.

Only if route E is selected, preview its authoritative plan without paid evaluation:

```bash
dbt-cortex-agent eval verify --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --suite <SUITE> --baseline-dir <BASELINE_DIR> --allow-target <TARGET> --allow-database <DATABASE> --json
```

### 6. Prepare optional Snowflake proof

Only when the user requests live proof, present separate exact plans for the needed boundary.

Package-native deployment manual parity:

```bash
dbt-cortex-agent agent deploy --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --connection <CONNECTION> --database <DATABASE> --role <ROLE> --warehouse <WAREHOUSE> --allow-target <TARGET> --allow-database <DATABASE> --apply --json
```

Runtime smoke manual parity:

```bash
dbt-cortex-agent agent smoke --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --version '<VERSION>' --question '<QUESTION>' --expect-tool <TOOL> --connection <CONNECTION> --database <DATABASE> --schema <AGENT_SCHEMA> --role <ROLE> --warehouse <WAREHOUSE> --allow-target <TARGET> --allow-database <DATABASE> --apply --json
```

Read version state first; replace `<VERSION>` with the observed immutable `VERSION$N`.
Use a bounded question and an exact declared tool name. Omit `--expect-tool` only when
the reviewed scenario intentionally needs no tool. Record consumer-role runtime
separately from deploy-role proof; API success does not establish CoWork UI success.

For route F, inspect current state with this read-only Snowflake operation (it also
parses locally; use reviewed connection context):

```bash
dbt-cortex-agent agent versions --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --connection <CONNECTION> --database <DATABASE> --role <ROLE> --warehouse <WAREHOUSE> --json
```

Choose exactly one applicable preview:

```bash
dbt-cortex-agent agent promote --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --version '<VERSION>' --alias <ALIAS> --connection <CONNECTION> --database <DATABASE> --role <ROLE> --warehouse <WAREHOUSE> --allow-target <TARGET> --allow-database <DATABASE> --json
dbt-cortex-agent agent rollback --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --to-version '<VERSION>' --alias <ALIAS> --connection <CONNECTION> --database <DATABASE> --role <ROLE> --warehouse <WAREHOUSE> --allow-target <TARGET> --allow-database <DATABASE> --json
dbt-cortex-agent agent drop --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --connection <CONNECTION> --database <DATABASE> --role <ROLE> --warehouse <WAREHOUSE> --allow-target <TARGET> --allow-database <DATABASE> --json
```

Promotion/rollback require an observed committed version. Add `--set-default` to
both preview and apply only when unversioned serving must move. After STOP 2, add
`--apply` to the exact reviewed command. Retirement additionally requires
`--confirm-agent <PHYSICAL_FQN>` matching the preview; explain that deletion removes
the Agent and its versions, not its data, stages, skills, or local files. Do not
delete/recreate an Agent merely to repair drift. Reinspect versions after routing
or absence after retirement. On partial failure, retain observed state and completed
phases, then request approval for a bounded retry; never claim transactional rollback.
Interrupted initial creation without persisted managed hashes requires explicit
recovery, not blind force/redeploy.

State which objects or runtime are affected, selected context, allowlists, and expected proof.
Present one boundary packet containing the objective, exact command, complete Snowflake scope,
expected proof, risks, and the single-command resume condition.

## STOP 2 — Snowflake mutation or runtime

Do not execute `--apply` for deployment, routing, retirement, skill smoke, or Agent smoke until the user
explicitly approves the exact command and Snowflake context. Approval of local
writes or a dry run does not satisfy this stop.

Resume only for the approved command. If its context, scope, or command changes, return to preview,
present a revised packet, and stop again.

### 7. Prepare optional paid evaluation

Require the already deployed Agent selected by the model, evaluation-stage access, explicit
connection/role/warehouse, target-resolved resource identities, and complete allowlists. The
package workflow materializes and tests the eval model before paid execution. Never propose a
second Agent deployment for this step. Show the exact suite,
metrics, row scope, prerequisites, and command:

`--database` selects connection context, not the only permitted resource database.
Repeat `--allow-database` for every reviewed Agent/dependency/stage/evaluation database.

```bash
dbt-cortex-agent eval verify --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --suite <SUITE> --baseline-dir <BASELINE_DIR> --connection <CONNECTION> --database <DATABASE> --role <ROLE> --warehouse <WAREHOUSE> --allow-target <TARGET> --allow-database <DATABASE> --apply --json
```

Present one boundary packet containing the objective, exact command, prerequisites and paid scope,
expected candidate proof, risks, and the one-run resume condition.

## STOP 3 — paid evaluation

Do not execute the paid eval command until the user explicitly approves this run and its stated
scope. Deployment or runtime approval does not approve evaluation spend.

Resume only for the approved run. If its prerequisites, row scope, metrics, context, or command
changes, present a revised packet and stop again. Report the candidate artifact and pass state
without moving a baseline.

### 8. Prepare optional baseline decision

First inspect the exact returned candidate and the selected baseline destination.
Require completed status, intrinsic pass, complete scored evidence, and no observed
Agent-version or dataset drift. Report infrastructure failures and quality rejections
separately. Do not use a directory glob to pick the newest candidate.

If an established baseline exists in the chosen directory, compare it explicitly:

```bash
dbt-cortex-agent eval gate <CANDIDATE_JSON> --baseline-dir <BASELINE_DIR> --json
```

If no baseline exists, skip the baseline gate; use the candidate's intrinsic
threshold/provenance evidence and report that regression is not yet established.
For either case, preview acceptance:

```bash
dbt-cortex-agent eval accept-baseline <CANDIDATE_JSON> --baseline-dir <BASELINE_DIR> --json
```

This preview does not prove acceptance eligibility or report an exact destination
when `baseline` is null. Review the artifact and derive the destination from the
baseline root plus target/database/schema/object/suite identity:
`<BASELINE_DIR>/<target>/<database>/<schema>/<object>/<suite>.json`.
Use the candidate's resolved identity, not its logical Agent name. Check whether
that file exists before approval.
Explain threshold/regression evidence, destination, overwrite status, and why movement is justified.
Never respond to a failure by rerunning until green or silently widening tolerance.
Present one boundary packet containing the objective, exact artifact and command, policy scope,
expected proof, risks, and the one-movement resume condition.

## STOP 4 — baseline movement

Do not accept, overwrite, migrate, or otherwise move a baseline until the user explicitly approves
the exact artifact, destination, and policy effect. Paid-run approval does not satisfy this stop.

Resume only for the approved one-movement command. If the artifact, destination, policy effect, or
command changes, present a revised packet and stop again. Then show and execute only the reviewed
manual parity command:

```bash
dbt-cortex-agent eval accept-baseline <CANDIDATE_JSON> --baseline-dir <BASELINE_DIR> --apply --json
```

For replacement, obtain explicit overwrite approval and use the same command with
`--force --apply`. `--force` is invalid in preview and never authorizes a failed
candidate or policy relaxation. Preserve the previous baseline through the adopter's
review/version-control policy and report the exact written path.

## Stopping points

- Stop 1: before any local project write or dependency installation.
- Stop 2: before any Snowflake mutation or live runtime invocation.
- Stop 3: before every paid evaluation run.
- Stop 4: before every baseline policy movement.

Each approval applies to one presented scope only. Never combine or infer approvals.

## Output

Report:

- objective, chosen route, levers, data, and proof status;
- files changed and dbt-owned metadata created;
- exact manual commands shown and commands actually run;
- parse/validate/render/package-deploy-preview/eval-verify-preview results;
- approvals received and boundaries not crossed;
- remaining blockers or optional next boundary.

Distinguish instruction/command tests, generated-project tests, observed assistant
behavior, and live proof. Passing package tests does not prove skill routing or
approval adherence in an actual assistant transcript. This is a repository-local
skill; installing the Python wheel does not register it in Cortex Code or publish
it to a skill catalog.
