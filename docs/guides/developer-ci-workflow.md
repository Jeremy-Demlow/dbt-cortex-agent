# Developer and CI/CD workflow

This is the canonical executable path for building, testing, shipping, and
retiring a dbt-owned Cortex Agent. Substitute project-specific values; never
copy the example policy unchanged into production.

Prerequisites for this golden adopter path: an existing dbt project, matching
Python/dbt package versions, `dbt-snowflake`, Snow CLI, and a reviewed `sandbox`
profile. Every command below uses that same target. The examples assume database
`ANALYTICS_DEV`, target schema `DEV`, default dbt schema generation, and scaffolded
custom schema `AGENTS`, resolving to `ANALYTICS_DEV.DEV_AGENTS.FINANCE_ASSISTANT`.
Check `agent deploy --json`'s `agents[].physical_fqn` before applying; substitute
your actual resolved schema and FQN for smoke and retirement if naming differs.
Live steps additionally need approved authentication, operation-specific roles,
warehouse, schemas, dependency access, and grants provisioned by the adopter.

> **dbt is the system of record. The manifest is the contract. Layout is
> convention.**

```text
dbt models + metadata + ref() edges
                  |
                  v
        target/manifest.json
                  |
        +---------+---------+
        |                   |
        v                   v
dbt materialization   dbt-cortex-agent CLI
owns Agent DDL        owns planning/orchestration
        |                   |
        v                   +--> skill upload
CREATE / ALTER / DROP       +--> runtime and SSE
VERSION$N and routes        +--> evaluation and evidence
```

Python contains no mutating Agent DDL. A direct lifecycle command resolves the
logical Agent from a fresh manifest, checks the operation boundary, and invokes
dbt for mutation. The CLI is the reusable product interface, not a replacement
source of Agent state.

## Install one release

These pins define the matched 0.0.12 release contract and require published
availability; see [installation](../getting-started/installation.md) and
[releasing](releasing.md) for the pending gates. Changing a dbt model still
requires its own adopter verification.

```bash
python -m pip install 'dbt-cortex-agent[runtime]==0.0.12'
```

```yaml
packages:
  - git: https://github.com/Jeremy-Demlow/dbt-cortex-agent.git
    revision: v0.0.12
```

The Python package coordinates files, dbt, runtime calls, and evidence. The dbt
package owns Agent DDL, immutable versions, aliases, DEFAULT, and retirement.

## Create an Agent

An Agent does not require a Semantic View. Start with a generic model:

```bash
dbt-cortex-agent agent scaffold --project-dir . --target sandbox --agent finance_assistant --json
dbt-cortex-agent agent scaffold --project-dir . --target sandbox --agent finance_assistant --apply --json
```

Add `--semantic-view-model sem_finance` only when a dbt Semantic View already
defines the governed domain. Add `--with-eval` only when representative questions
and ground truth are available. Experimental Agent specification keys remain
editable full-body YAML; the package does not expose private-preview-specific
scaffold flags.

The generated directory is a convention. Discovery comes from the parsed dbt
resource, not its path:

```text
models/agents/finance_assistant/
|-- finance_assistant.sql
|-- agent.yml
`-- skills/
    `-- README.md
```

## Validate without Agent mutation

This section is not a no-write or guaranteed-offline path. `dbt deps` may fetch
packages and writes dependencies; fresh parse writes manifests and logs. Compile
writes compiled artifacts and can open the Snowflake adapter, including with
`--no-introspect`. Run compile only with separately approved connection access;
credential-free CI uses parse and local deterministic tests instead. Do not run
unreviewed consumer hooks/macros as part of an allegedly effect-free check.

```bash
dbt deps --project-dir .
dbt-cortex-agent doctor --project-dir . --target sandbox --json
dbt-cortex-agent manifest validate --project-dir . --target sandbox --agent finance_assistant --json
dbt compile --project-dir . --target sandbox --select finance_assistant
dbt-cortex-agent agent deploy --project-dir . --target sandbox --agent finance_assistant --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

Machine-readable checkpoints: doctor returns `passed`; manifest validation lists
the selected `agents`; deploy preview has `applied: false`, resolved
`agents[].physical_fqn`, `resource_databases`, and `dbt_selection`. A preview is
not deployment or runtime evidence. Compilation output needs separate review.

## Deploy and ask

```bash
dbt-cortex-agent agent deploy --project-dir . --target sandbox --agent finance_assistant --connection sandbox --database ANALYTICS_DEV --role AGENT_DEPLOYER --warehouse AGENT_WH --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
dbt-cortex-agent agent smoke --project-dir . --target sandbox --agent finance_assistant --question 'What can you help me answer?' --connection sandbox --database ANALYTICS_DEV --schema DEV_AGENTS --allow-target sandbox --allow-database ANALYTICS_DEV --apply
```

Human smoke output is answer-first and bounded. Use `--json` for normalized
automation output. Runtime and deployment are separately approved operations.
Use `--version 'VERSION$N'` to prove an exact immutable candidate and
`--expect-tool <tool_name>` to make routing part of the smoke contract. Raw SSE
evidence is opt-in through `--raw-events <filename>`; the package does not emit
raw protocol traffic by default.

Applied deploy JSON retains `phases`; a controlled partial failure includes
`status: partial_failure` and completed work. Applied smoke JSON has `passed`
and a normalized `response`; preview leaves both null. Runtime inference and
warehouse work may incur costs independently of native Agent Evaluation.

## Configurable client budget (0.0.12)

Version 0.0.12 adds `--timeout-seconds` to `agent smoke` and `skill smoke`.
It is not supported by 0.0.11. After installing matching 0.0.12 artifacts,
choose an explicit finite-positive budget for a multi-tool investigation:

```bash
dbt-cortex-agent agent smoke --project-dir . --target sandbox --agent finance_assistant --version 'VERSION$2' --question 'Summarize the evidence and identify missing facts.' --timeout-seconds 300 --connection sandbox --database ANALYTICS_DEV --schema DEV_AGENTS --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

This preview shows `timeout_seconds: 300` and does not invoke the Agent. Review
the destination, version, question and cost allowance before adding `--apply`.
Agent smoke returns `passed`, `response`, and the effective budget. Skill smoke
returns `verified` plus `failure` containing the failed skill, Agent, error and
partial response; it stops without invoking later skills. An expected tool name
does not prove a correct answer. Inspect skill identity, loaded content, final
facts, and per-question evaluation evidence separately.

The default remains 60 seconds for compatibility. Each skill gets a fresh
budget; several skill checks may take longer than this total. Setup and response
streaming count, but dbt parsing and evaluation polling do not. Heartbeats do not
renew the budget. Blocking calls and cleanup can overrun. A local timeout is not
proof that the server stopped or spending ceased. Retain evidence and reconcile
the original request before approving another call. See [troubleshooting](../troubleshooting.md).

Raw events, when requested, are written beneath
`<artifact-dir>/raw-events/<filename>`; default root is
`<project-dir>/target/dbt_cortex_agent`. Use unique filenames because collisions
fail before invocation. Keep responses and trace artifacts private.

## Understand what deployment commits

The materialization adapts dbt desired state to Snowflake's LIVE draft and
immutable version lifecycle:

```text
Agent absent
  -> deploy source A -> VERSION$1
  -> change source
  -> deploy source B -> VERSION$2
  -> roll back serving to VERSION$1
  -> unchanged deploy of source B -> no VERSION$3
  -> roll forward by routing to existing VERSION$2
```

Content identity is independent of serving DEFAULT. A rollback changes routing,
not source content, so an unchanged redeployment must not create a duplicate
version. Applied deployment reports completed durable phases such as
`version_committed`, `metadata_reconciled`, `alias_reconciled`, and
`live_reconciled`. A later failure does not erase an earlier durable phase.

## Evaluate

```bash
dbt-cortex-agent eval verify --project-dir . --target sandbox --agent finance_assistant --suite core --baseline-dir baselines --allow-target sandbox --allow-database ANALYTICS_DEV --json
dbt-cortex-agent eval verify --project-dir . --target sandbox --agent finance_assistant --suite core --baseline-dir baselines --connection sandbox --database ANALYTICS_DEV --role AGENT_EVALUATOR --warehouse AGENT_WH --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
dbt-cortex-agent eval accept-baseline <candidate.json> --baseline-dir baselines --apply --json
```

The evaluation stage must already exist. Paid verification never deploys an
Agent, and baseline acceptance is a separate policy decision.
The `core` suite examples require the optional evaluation scaffold (or an existing
suite), authored representative ground truth, thresholds, and any reviewed
baseline. Bare scaffold alone does not create a runnable evaluation suite.
Verify preview returns `applied: false` and `passed: null`; an applied verification
retains per-suite candidate paths and separates execution from gate outcomes.

For version-targeted proof, add `--version 'VERSION$2'` to `eval verify` or
`eval run` only after observing that committed version. Without it, DEFAULT
provenance must remain stable. Inspect all per-question observations as well as
configured aggregate floors. A floor PASS without an accepted baseline is not
regression-to-baseline proof. Candidate JSON defaults to
`target/dbt_cortex_agent/candidates/<target>/<database>/<schema>/<object>/<suite>/<run_name>.json`.
The accepted baseline uses the corresponding `baselines/.../<suite>.json` path;
`--baseline-dir` overrides that root, not the identity hierarchy. Gate/compare
operate on local artifacts and do not invoke the Agent. Keep baseline acceptance
out of automatic retry/recovery.

Version 0.0.12 supports opt-in `questions[].thresholds` through the CLI, keyed
by stable `ground_truth_ref`. A failing protected observation blocks a gate even
if averages pass. Nonempty policies use replayable schema-v3 candidate/baseline
evidence; absent/empty policies keep schema v2. Native macro run/gate rejects
the opted-in policy before effects. See [question floors](evaluations.md#opt-in-question-floors-0012);
offline tests and release smoke do not establish paid native evaluation quality.

## Promote and roll back

```bash
dbt-cortex-agent agent versions --project-dir . --target sandbox --agent finance_assistant --connection sandbox --json
dbt-cortex-agent agent promote --project-dir . --target sandbox --agent finance_assistant --version 'VERSION$2' --alias production --set-default --connection sandbox --database ANALYTICS_DEV --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
dbt-cortex-agent agent smoke --project-dir . --target sandbox --agent finance_assistant --version 'VERSION$2' --question 'What can you help me answer?' --connection sandbox --database ANALYTICS_DEV --schema DEV_AGENTS --allow-target sandbox --allow-database ANALYTICS_DEV --apply
dbt-cortex-agent agent rollback --project-dir . --target sandbox --agent finance_assistant --to-version 'VERSION$1' --alias production --set-default --connection sandbox --database ANALYTICS_DEV --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
```

Rollback moves routing and preserves newer immutable versions. Re-promoting
`VERSION$2` reuses it; it does not create `VERSION$3`.
These commands require observed `VERSION$1` and `VERSION$2` from two distinct
deployed specifications; do not infer those versions from the examples.

After rollback, repeat the reviewed deploy preview and, if approved, deployment
of unchanged source. Compare version inventory before/after and the returned
reconciliation phases: unchanged content must not create a duplicate version.
Roll forward by promoting the existing version, then read inventory again to
verify DEFAULT and serving alias. Runtime calls are separately costed; reading
routes is not proof of the answer served through an application or UI.

Alias movement is not transactional. The package validates the target and
planned source state, performs the required durable operations, verifies alias
and DEFAULT postconditions, and reports partial state. After a failure, inspect
the returned state and retry the same desired route instead of assuming an
automatic rollback.

### Custom aliases and subsequent deployments

`--alias production` is an explicit routing operation, not a model change.
Do not assume PRODUCTION and the model's configured alias (for example LATEST)
coexist independently on the same version. In the prior native observation
reported for this workflow, assigning PRODUCTION to V2 displaced LATEST on V2.
A subsequent unchanged deploy restored LATEST to V2 and displaced PRODUCTION,
without creating V3 or issuing a DEFAULT change. The dbt materialization always
enables model-alias reconciliation, including on unchanged content. This
observation is not a universal native-platform guarantee; inspect the alias
inventory in your deployment environment.

The examples above explicitly use `--set-default`; custom-alias-only promotion
omits that option. With DEFAULT explicitly pinned to V1 and desired content at
V2, alias-only promotion and model-alias restoration leave DEFAULT at V1. The
unchanged deploy reuses managed V2 content even though DEFAULT serves V1.
Content idempotency does not mean every alias remains unchanged. Only the
lower-level `cortex_agent__apply_deploy` helper accepts `reconcile_alias=false`
to leave the custom alias alone on unchanged content; this is not a CLI option
or a project variable. Changed-content deployment still reconciles the model
alias. See [lifecycle guidance](lifecycle.md#custom-alias-reconciliation).

Read `agent versions --json` before and after promotion and the next deploy;
check `aliases`, `default_version`, and the committed-version inventory. If you
require the PRODUCTION name after model-alias restoration, explicitly reapply
the reviewed promotion and inspect again. That can displace LATEST in the
observed behavior, so do not create an automatic deploy/promote reconciliation
loop or treat a custom alias as a durable DEFAULT pin.

When checking specifications, distinguish the serving version from the draft.
In the prior reported observation, unversioned `DESCRIBE AGENT <fqn>` returned
the DEFAULT specification, not the editable LIVE specification. With DEFAULT
pinned to V1 and LIVE containing V2, that read can show V1 without implying that
V2 failed to deploy. Inspect the explicitly selected committed version and LIVE
separately; an alias inventory is not runtime-answer proof. The local regression
models the observed alias and pin behavior; it does not rerun native DESCRIBE or
qualify specification-selection behavior across platform versions.

## Retire deliberately

```bash
dbt-cortex-agent agent drop --project-dir . --target sandbox --agent finance_assistant --confirm-agent ANALYTICS_DEV.DEV_AGENTS.FINANCE_ASSISTANT --connection sandbox --database ANALYTICS_DEV --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
```

Removing a dbt model never drops its Agent. The guarded command removes only the
Agent and its versions. Source files, Semantic Views, Cortex Sense contexts,
Search services, stages, skills, MCP servers, evaluations, candidates, and
baselines remain.

## CI/CD split

```text
pull request
  install -> deps -> parse -> doctor -> tests -> deploy/eval previews
  compile only where adapter connection access is separately approved

protected deployment
  complete allowlists -> deploy --apply -> version-specific smoke
  -> optional paid eval verify -> retained evidence

release
  build one wheel -> offline matrices -> installed-consumer proof
  -> protected zero-state V1/V2/promote/rollback/drop proof
  -> publish that exact wheel from the already matching immutable dbt tag
```

Pull requests should maximize offline confidence by default. Protected jobs
cross deployment, runtime, and paid boundaries separately and retain package
version, target, physical Agent FQN, immutable candidate version, normalized
specification hashes, completed durable phases, smoke assertions, evaluation
suite identity, and structured outcomes. Jobs for different Agents may run in
parallel; jobs addressing the same Agent need a shared concurrency key.

Main reconciles every enabled Agent to current desired state but does not need
to repeat every paid evaluation. Package release qualification is a third lane:
it builds one wheel, installs that exact artifact into clean consumer fixtures,
proves zero-state V1/V2/promotion/rollback/no-op/drop behavior, and only then
publishes the Python artifact. The Git tag and GitHub release record already
exist when the release live gate starts. Installed-consumer matrices are package
CI checks; they must also pass for the release candidate. Native paid-evaluation
quality is not qualified by this lifecycle proof (`paid_evaluation: false`).

## Authentication, authorization, and wrappers

A named Snow CLI connection determines how and who authenticates. The dbt
target determines where dbt intends to build. Repeatable allowlists determine
where this invocation is permitted to operate. Snowflake RBAC determines what
the principal can actually do. These controls are complementary.

`--database` sets the connection/default execution context. It does not assert
that every selected Agent and dependency lives in that database. Package-native
deployment carries each manifest-resolved resource database through planning and
requires every one to appear in the repeatable `--allow-database` values.

The supported connection bridge accepts `SNOWFLAKE_JWT` with account, user, and
a file-based private key, and `WORKLOAD_IDENTITY` when supplied by the execution
environment. Unsupported password, OAuth, and external-browser modes fail
closed rather than being silently treated as equivalent. Infrastructure such as
databases, schemas, roles, warehouses, stages, Semantic Views, Search services,
and evaluation stages remains owned outside this package.

No Makefile or copied Python sequencer is required. An adopter may wrap the
direct commands to inject reviewed target, role, warehouse, fleet scope,
approvals, or report retention, but the wrapper must delegate package behavior:

```text
human or CI
    +--> dbt-cortex-agent ...
    `--> adopter wrapper --> dbt-cortex-agent ...
```

If a plain package command can do it, that is product behavior. Fleet selection,
team approvals, and repository-specific reporting are adopter policy.

Exit `0` means success, `1` means completed diagnostic/quality failure, and `2`
means controlled configuration, infrastructure, or runtime failure. Agent DDL is
non-transactional: retry from inspected state rather than assuming rollback.