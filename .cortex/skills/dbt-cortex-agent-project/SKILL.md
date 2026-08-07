---
name: dbt-cortex-agent-project
description: "Guide adoption or migration of a dbt-owned Snowflake Cortex Agent with dbt_cortex_agent 0.3.1. Use when a user wants to add Cortex Agents to a new or existing dbt project, adopt an existing semantic view, try the Orders starter, migrate an existing Agent into dbt, or optionally author manifest-owned Agent evaluations. Triggers: adopt dbt cortex agent, add cortex agent to dbt, migrate cortex agent to dbt, author dbt agent evaluation, dbt agent project, orders agent starter."
---

# dbt Cortex Agent project adoption

Guide one project from evidence to a dbt-owned Agent. Cortex Code performs discovery,
edits, and verification; every executable package step also shows the exact manual
command. This skill is guidance only: do not create wrapper scripts or duplicate Agent
lifecycle logic.

## Authority and invariants

- Use `dbt_cortex_agent` **0.3.1** commands and metadata contracts.
- dbt Core with `dbt-snowflake` is authoritative for parse, graph, manifest, and release
  proof. Fusion/fdbt may provide advisory feedback but never replaces dbt Core evidence.
- dbt owns Agent/eval definitions, rendering, physical naming, lifecycle macros, versions,
  aliases, grants, and eval plans. The CLI coordinates those contracts.
- Let manifest-dependent commands run their normal fresh parse. Never bypass parsing.
- Discover target, database, schemas, connection, warehouse, role, Agent names, semantic
  views, and safety allowlists from the project and user. Do not invent environment values.
- Preview is evidence, not approval for a later write, mutation, runtime, spend, or policy
  boundary.

## Workflow

### 1. Discover the project read-only

Use Cortex Code file and search tools to inspect, without editing:

1. Repository instructions and contribution rules.
2. `dbt_project.yml`, dependency declarations, profile/target conventions, and dbt version.
3. Semantic-view models, Agent exposures, eval models, tests, and generated manifest if present.
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
- **Assembly line:** metadata -> parse -> validate -> render -> deploy preview -> optional
  approved deploy/runtime -> optional approved eval -> separately approved baseline policy.

If objective, controllable lever, or supporting data is missing, stop with a concise gap report.

### 3. Select one adoption route

Choose from discovered evidence and user intent. Do not combine routes unless needed.

#### A. Existing semantic view

Use when a dbt semantic-view model already represents the governed domain.

Plan an Agent exposure under the consumer project's conventions with:

- `config.meta.cortex_agent.enabled: true`;
- `depends_on` containing `ref('<SEMANTIC_VIEW_MODEL>')`;
- an Analyst tool whose `semantic_view_model` is that dbt model name, not a hardcoded FQN;
- objective-aligned orchestration and response instructions;
- project-selected physical naming and usage roles only when evidence provides them.

#### B. Fixed Orders starter

Use only for the package-owned synthetic tutorial. It is not a generic wizard and must not be
adapted into inferred business semantics.

Preview package/dependency, safety-var, seed, semantic-view, Agent, eval, and `.dbtignore`
actions:

```bash
dbt-cortex-agent init --project-dir <PROJECT_DIR> --starter orders --package-source <PACKAGE_GIT_URL> --revision v0.3.1 --target <TARGET> --allow-target <TARGET> --allow-database <DATABASE> --json
```

#### C. Existing Agent migration

Use when an Agent exists outside dbt. Read its provided definition and map it into one exposure;
do not write a lifecycle importer or infer missing business meaning.

Create a migration table for review:

| Existing concern | dbt-owned destination |
|---|---|
| Instructions | `config.meta.cortex_agent.instructions` |
| Analyst tool | `tools[].semantic_view_model` plus `depends_on` |
| Search/tool config | supported exposure tool metadata |
| Physical name | `snowflake_name` or target naming map |
| Usage roles | `access.usage_roles` |
| Skills/MCP | supported canonical metadata; excluded from native eval |
| Versions/aliases/grants | existing package lifecycle commands after approval |

Flag unsupported or unavailable fields. Preserve the existing live Agent until dbt render and an
approved migration plan prove parity; never mutate it during discovery or authoring.

#### D. Optional evaluation authoring

Add this route only when representative questions and ground truth exist. Plan a table model with
`config.meta.cortex_eval`, stable question IDs/refs, `native_eval` projection, metrics, thresholds,
and regression tolerances. Each row must emit one `OUTPUT` VARIANT. Use
`ground_truth_output` for answer correctness and `ground_truth_invocations` for tool metrics;
expected tool names must match projected tool names exactly.

Skills and MCP behavior require separate smoke/integration proof because native Agent Evaluation
does not cover them.

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

For route B, manual command parity is the reviewed preview plus `--apply`:

```bash
dbt-cortex-agent init --project-dir <PROJECT_DIR> --starter orders --package-source <PACKAGE_GIT_URL> --revision v0.3.1 --target <TARGET> --allow-target <TARGET> --allow-database <DATABASE> --apply --json
```

For routes A, C, or D, use Cortex Code file tools to make only the approved metadata/model/test
changes. Do not generate scripts. Add the pinned package dependency and explicit safety vars only
when absent; preserve adopter configuration.

Then show manual local verification parity:

```bash
dbt deps --project-dir <PROJECT_DIR>
dbt parse --project-dir <PROJECT_DIR> --target <TARGET>
dbt-cortex-agent doctor --project-dir <PROJECT_DIR> --target <TARGET> --json
dbt-cortex-agent manifest validate --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --json
dbt-cortex-agent agent render --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --projection canonical --json
dbt-cortex-agent agent render --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --projection native_eval --json
dbt-cortex-agent agent deploy --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --projection canonical --allow-target <TARGET> --allow-database <DATABASE> --json
```

Run the applicable commands through Cortex Code. The deploy command above is a preview: it does
not mutate Snowflake without `--apply`. Report parse, validation, rendered identities/specs, planned
mutation, and failures. Do not paper over dbt Core failures with advisory Fusion/fdbt output.

If route D is selected, preview its authoritative plan without spend:

```bash
dbt-cortex-agent eval run --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --suite <SUITE> --json
```

### 6. Prepare optional Snowflake proof

Only when the user requests live proof, present separate exact plans for the needed boundary.

Deployment manual parity:

```bash
dbt-cortex-agent agent deploy --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --projection canonical --connection <CONNECTION> --database <DATABASE> --allow-target <TARGET> --allow-database <DATABASE> --apply --json
```

Runtime smoke manual parity:

```bash
dbt-cortex-agent agent smoke --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --question <QUESTION> --projection canonical --connection <CONNECTION> --database <DATABASE> --schema <AGENT_SCHEMA> --allow-target <TARGET> --allow-database <DATABASE> --apply --json
```

State which objects or runtime are affected, selected context, allowlists, and expected proof.
Present one boundary packet containing the objective, exact command, complete Snowflake scope,
expected proof, risks, and the single-command resume condition.

## STOP 2 — Snowflake mutation or runtime

Do not add or execute `--apply` for deploy, grant, promote, rollback, skill upload/smoke, or Agent
smoke until the user explicitly approves the exact command and Snowflake context. Approval of local
writes or a dry run does not satisfy this stop.

Resume only for the approved command. If its context, scope, or command changes, return to preview,
present a revised packet, and stop again.

### 7. Prepare optional paid evaluation

Require an already deployed native-eval Agent, materialized eval table, evaluation stage access,
explicit connection/warehouse, matching target/database, and both allowlists. Show the exact suite,
metrics, row scope, prerequisites, and command:

```bash
dbt-cortex-agent eval run --project-dir <PROJECT_DIR> --target <TARGET> --agent <AGENT> --suite <SUITE> --connection <CONNECTION> --database <DATABASE> --warehouse <WAREHOUSE> --allow-target <TARGET> --allow-database <DATABASE> --apply --json
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

First preview policy effects with the candidate:

```bash
dbt-cortex-agent eval gate <CANDIDATE_JSON> --json
dbt-cortex-agent eval accept-baseline <CANDIDATE_JSON> --baseline-dir <BASELINE_DIR> --json
```

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
- parse/validate/render/deploy-preview/eval-plan results;
- approvals received and boundaries not crossed;
- remaining blockers or optional next boundary.
