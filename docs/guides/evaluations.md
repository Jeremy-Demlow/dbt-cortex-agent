# Evaluations

An optional evaluation suite is a table model with `config.meta.cortex_eval`. dbt owns the
suite, native configuration, same-Agent target identity, metric policy, and public macros.
The Python CLI consumes one dbt-rendered execution plan and adds bounded polling,
retry, durable candidate artifacts, comparison, gates, and accepted baselines.

## Prerequisites and spend boundary

Before a paid CLI run, provide all three prerequisites:

1. the **normally deployed Agent** selected by the full-body model and target;
2. a **materialized eval table** with `INPUT_QUERY` and `OUTPUT` VARIANT rows;
3. access to the **evaluation stage** resolved as
   `<resolved Agent database>.<resolved Agent schema>.EVAL_CONFIG_STAGE`
   (or the explicitly configured stage in the execution plan).

Evaluation never creates, deploys, replaces, or otherwise mutates that Agent. The
eval table FQN comes from the resolved dbt model in `cortex_eval_schema`. Dataset names are content-hashed from
the Agent/suite identity so changed ground truth does not silently reuse a stale
Snowflake dataset.

`dbt-cortex-agent eval run` does not create these prerequisites. Its default path
only renders the authoritative plan. `--apply` checks the pre-existing stage,
uploads a generated JSON config, starts Snowflake Agent Evaluation, and incurs Cortex
and warehouse spend. Applied execution requires explicit `--connection` and
`--warehouse`, `--target`, `--database`, and matching repeatable `--allow-target`
and `--allow-database` values. The plan target and database must match the
configured context and both allowlists before the connector is loaded. The CLI
then sets the dbt-rendered plan role before warehouse, database, and schema.

For the complete package-owned workflow, `eval verify` materializes and tests
the selected eval model before starting native evaluation, then consumes the
exact candidate and applies intrinsic or accepted-baseline policy. It still
never deploys or changes the Agent.

## Python client path

Render the plan without spend:

```bash
dbt-cortex-agent eval run --project-dir . --target sandbox \
  --agent orders_assistant --suite core --json
```

Compile the normal Agent specification without mutation:

```bash
dbt compile --project-dir . --profiles-dir . --target sandbox \
  --select orders_assistant
```

After review, upload declared skills and run dependency-aware `dbt build
--select +orders_assistant` with the approved profile and allowlists. Evaluation
remains a separate optional paid operation and never calls the Agent lifecycle.

After deploying that Agent and materializing/testing the eval model, an approved
paid run uses:

```bash
dbt-cortex-agent eval run --project-dir . --target sandbox \
  --agent orders_assistant --suite core --connection sandbox \
  --database ANALYTICS_DEV --warehouse EVAL_WH \
  --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
```

The composed equivalent is:

```bash
dbt-cortex-agent eval verify --project-dir . --target sandbox \
  --agent orders_assistant --suite core --connection sandbox \
  --database ANALYTICS_DEV --role EVAL_ROLE --warehouse EVAL_WH \
  --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
```

If no accepted baseline exists, intrinsic thresholds determine the outcome and
JSON reports `baseline_state=not_established`. A completed quality failure exits
`1`; a controlled configuration or infrastructure failure exits `2`. Baseline
acceptance remains a separate reviewed operation.

The CLI parses, calls `cortex_eval__execution_plan`, verifies plan identity and
signature, proves the Agent exists with a DEFAULT version before upload/START,
validates live table rows, records the pre-run DEFAULT Agent version,
starts/polls the evaluation with bounded transient retry, records post-run
provenance, and writes a candidate JSON under `target/dbt_cortex_agent` unless
`--artifact-dir` overrides it. Without `--version`, DEFAULT drift makes the
result indeterminate.

## Choosing the Agent version and the judges

Without `--version`, Snowflake evaluates whatever an unversioned request reaches:
LIVE while the Agent has one version, DEFAULT after that.

The candidate's `evaluated_version` is what Snowflake recorded, not what was
requested. After the run, the CLI reads the run's trace spans through
`SNOWFLAKE.LOCAL.GET_AI_OBSERVABILITY_EVENTS`
(`snow.ai.observability.object.version.name`; the eval role already holds
`MONITOR` on the Agent) and records `evaluated_version_source: run_trace` and
`observed_versions`. A run whose traces show another version, more than one, or
none is written as `indeterminate` and failed: its evidence is kept, but it
cannot gate or become a baseline.

Pass `--version VERSION$N` to `eval run` or `eval verify` to score one committed
version instead. Only `VERSION$N` is accepted: aliases and the `LIVE`, `FIRST`,
`LAST`, and `DEFAULT` shortcuts can point somewhere else on the next run. The CLI
writes `agent_params.agent_version` into the staged config for that run only and
checks `SHOW VERSIONS IN AGENT` before every START. The version is not part of the
signed plan, so a baseline accepted on `VERSION$1` gates a candidate on
`VERSION$2`. The candidate records `requested_version` and the traced
`evaluated_version`; `eval verify` refuses a candidate whose `requested_version`
differs from the one it asked for. A DEFAULT move during a pinned run is recorded in
`default_version_changed` but does not void the result, because DEFAULT was not
the version under test.

Pin the judges in the suite metadata as well. A system metric written as a
mapping takes `name` and `version` only (`auto`, `v<major>`, or
`v<major>_<minor>`). A custom metric takes an optional `model`:

```yaml
metrics:
  - name: answer_correctness
    version: v3
  - name: tool_selection_accuracy
    version: v3
  - name: boundary_adherence
    model: claude-sonnet-4-6
    score_ranges: {min_score: [1, 2], median_score: [3, 3], max_score: [4, 5]}
    prompt: |
      ...
```

Plain metric names and custom metrics without `model` use Snowflake's current
default judge, which rolls forward when that judge's model is deprecated; `v3`
also picks up later `v3_<minor>` releases. Pin `v<major>_<minor>` where scores
must stay comparable. Because metric declarations are signed, changing a
declaration changes the suite signature. Candidates record the declared
selectors as `metric_judges` and, from the run's eval spans, the judge that
actually scored each metric as `observed_metric_judges`
(`{judge, version}`, for example `{"judge": "claude-sonnet-4-6", "version":
"v3_0"}`; custom metrics report a judge and no version). When both artifacts
have observed judges, `eval compare` uses them, so two runs that declared `v3`
but were scored by different minor versions report `metric judges changed`
instead of comparing their scores. Older artifacts fall back to the declared
selectors.

The default artifact root is resolved relative to `--project-dir`. An applied
run writes
`target/dbt_cortex_agent/candidates/<target>/<database>/<schema>/<object>/<suite>/<run_name>.json`. Accepted
baselines default to
`target/dbt_cortex_agent/baselines/<target>/<database>/<schema>/<object>/<suite>.json`; `--artifact-dir` moves
both defaults, while `--baseline-dir` overrides the baseline root for the
baseline command being run.

With `--json`, preview returns one object containing `command`, `plan`, a null
`candidate`, and `passed: null`; applied execution replaces `candidate` with the
written path and reports its pass state. Without `--json`, `eval run` still
prints the plan as JSON for review and prints `Candidate: <path>` after an
applied run. dbt parse and macro details remain in dbt output/logs; candidate and
baseline files are the durable evaluation evidence.

Candidate schema v2 includes the same `agent_fqn`, plan/suite signatures, ordered
ground-truth refs, metrics, thresholds, regression tolerances, row evidence,
pre/post DEFAULT version provenance, the requested and traced Agent versions,
and the declared and observed judge for each metric. It contains only
single-Agent identity.

```bash
dbt-cortex-agent eval gate candidate.json --json
dbt-cortex-agent eval compare baseline.json candidate.json --json
dbt-cortex-agent eval accept-baseline candidate.json
```

Baseline acceptance is preview-only until `--apply`; `--force` also requires
`--apply`. A candidate cannot widen accepted baseline tolerances. A baseline move
is a reviewed policy decision, never an automatic response to a failed gate.

### Gate eligibility and result completeness

Comparison, gating, verification (including runs without an accepted baseline),
and baseline acceptance require `status: completed` and `passed: true` exactly.
Good averages cannot override an intrinsic failure or DEFAULT-version drift.
Threshold and regression-tolerance keys must name declared metrics; the Python
execution-plan and apply preflights reject unknown keys before build or paid work.

Native aggregate observations are joined by the already-unique source
`INPUT_QUERY` to the declared `ground_truth_ref` using an immutable local snapshot
of all validated input/ref/test_type entries captured before START, not a later
read of the source table. Completeness requires exactly
one finite `eval_agg_score` for each applicable ref/metric pair. Native
`RECORD_ID` and `INPUT_ID` are retained as evidence, not assumed to identify
questions; `total_records` counts distinct ground-truth refs. Duplicate pairs
fail even when their native IDs differ. Missing, unknown, or ambiguous refs and
metrics fail closed. Candidate summaries and counts must agree with row evidence.

The existing boundary rule applies only to `tool_selection_accuracy` and
`tool_execution_accuracy` (`TOOL_METRICS`): when source `test_type` is not
`in_scope`, these observations are excluded from scoring and required-score
coverage. Their rows may be absent or carry null/nonfinite scores. Duplicate
excluded observations or inconsistent test types still fail. Answer correctness
and custom metrics remain required on boundary rows. If every observation for a
tool metric is excluded, that metric cannot satisfy an explicit threshold or
regression policy. Every declared ref must still be represented; an entirely
absent boundary ref is not inferred from other results.

Malformed/incomplete candidate evidence is a controlled validation failure;
valid but non-passing or indeterminate evidence is a failed quality gate. Compact
baselines continue to omit raw rows, so their finite summaries/counts and
eligibility can be checked but their historical row grain cannot be reconstructed.
Older candidates without complete row evidence must be regenerated rather than
silently treated as passing. These rules have local fixture-based regression
coverage; they are not a new live Snowflake qualification claim.

### Source Rebuilds And Snapshot Evidence

The Python client compares its captured mapping before every START and after
polling/result collection. A pre-START mismatch stops execution. Observed later
drift makes a completed scored candidate `indeterminate` and failed; an incomplete
or failed run stops without a candidate or retry onto the changed source. Invalid
post-run mappings count as drift; source-query failures remain infrastructure
failures. Result-fetch retries always use the original snapshot.

New candidates retain `run_metadata.dataset_snapshot` as rows of
`[input_query, test_type, ground_truth_ref]` and a boolean `dataset_source_changed`.
Artifact validation checks complete unique mapping membership and exact result
input/ref/type agreement, and rejects a passing artifact with observed drift.
Schema-v2 baseline acceptance retains these metadata fields but still omits
scored rows; protected schema-v3 baselines retain rows for question-floor replay.
The fields are additive to schema v2: older artifacts without either field retain
existing validation, not retrospective snapshot proof. Regenerate an older
candidate when immutable annotation provenance is required; do not backfill its
mapping from today's source. This is consistency evidence, not tamper-proof signing.

START initiates native dataset ingestion from the configured table. These reads
do not transactionally freeze Snowflake, prove exactly when ingestion read that
table, or detect a change reverted between observations. Only the input/ref/type
mapping is compared, not all ground-truth OUTPUT content. Coordinate source
rebuilds externally when that stronger guarantee is required. This protection
applies to the Python client path, not the separate native macro gate below.

## dbt macro path

### Opt-in question floors (0.0.12)

Protect individual questions with `questions[].thresholds` in dbt-owned eval
metadata. Suite-wide `thresholds` still apply to averages; question floors apply
independently to the selected `ground_truth_ref`/metric observations. For example:

```yaml
metrics: [answer_correctness, tool_selection_accuracy]
thresholds: {answer_correctness: 0.6}
questions:
  - id: critical_answer
    ground_truth_ref: critical_answer_v1
    test_type: in_scope
    thresholds: {answer_correctness: 0.8, tool_selection_accuracy: 1.0}
  - id: ordinary_answer
    ground_truth_ref: ordinary_answer_v1
```

A critical score of 0.4 and ordinary score of 1.0 average to 0.7, satisfying the
suite floor but failing the critical floor. Equality passes. Missing, duplicate,
nonfinite, out-of-range or inapplicable protected observations fail validation;
editing `passed`, clearing failure lists, or replacing summaries cannot produce
a passing gate. The existing ref/metric completeness rules still apply.

Metric keys must be declared. Built-in floors are in [0, 1]. Custom metrics need
explicit finite, ordered min/median/max `score_ranges` pairs; their outer bounds
define the legal floor and protected score range. Tool-accuracy floors are rejected
for questions whose `test_type` is not `in_scope`; boundary answer/custom floors
remain valid. Before START, the client checks protected question types against
the captured dataset snapshot, and retained rows must match that applicability.

Nonempty policy uses plan and artifact schema v3, with `question_policy` version
1 containing `thresholds` (ref -> metric -> floor), `score_bounds` and `test_types`.
dbt includes the complete policy in `signature_material` and `suite_signature`.
Changing, lowering, removing or rekeying a policy is incomparable with an existing
baseline; `eval verify` also binds the exact policy to the current plan.
Protected v3 baselines retain complete scored rows so eligibility is replayable,
rather than trusting a historical pass flag or compact average. Existing v2
artifacts remain readable and unchanged; absent or empty question maps retain
the original v2 signature inputs, compact baselines and aggregate behavior.
There is no evidence backfill or automatic baseline migration. Older clients
reject v3 evidence; use matching 0.0.12 product code and macros for this policy.

Use `dbt-cortex-agent eval run/verify`, then artifact `compare/gate/accept-baseline`.
The native macro `cortex_eval__run` and `cortex_eval__gate` explicitly reject a
nonempty question policy before START or result queries, directing operators to
the CLI. Native dry-run previews and execution-plan rendering remain available;
direct START/config primitives are not quality gates. No native per-question
SQL gating or paid/live qualification is claimed. Retained evidence and MD5
suite signatures prove consistency, not authenticity against an actor rewriting
all local files. Keep baseline changes separately reviewed and source rebuilds
coordinated under the existing snapshot limitations above.

Use public macros when the complete workflow should remain in dbt:

```bash
dbt run-operation cortex_eval__execution_plan --target sandbox \
  --args '{"agent_name":"orders_assistant","suite_name":"core"}'
dbt run-operation cortex_eval__run --target sandbox \
  --args '{"model_name":"orders_assistant_core","dry_run":true}'
```

`cortex_eval__run` can render, start, poll, write Snowflake result rows, and apply
declared threshold gates. It is an on-demand native macro path; it does not write
the CLI's durable candidate/baseline artifacts or apply accepted-baseline policy.
Direct macro calls also rely on dbt's profile and package safety vars rather than
the CLI's explicit connection, resolved-database, and duplicate allowlist gates.
Unlike the Python CLI path, the native start macro issues `CREATE STAGE IF NOT
EXISTS` for its resolved config stage. This requires stage-creation privileges
when absent. Do not transfer that provisioning behavior to `eval run` or
`eval verify` CLI instructions; those require the stage already provisioned.

Native `cortex_eval__run` and `cortex_eval__start` dry runs use the real config
renderer's explicit `dry_run=true` path. It performs local metadata validation
but no content-hash, dataset-inventory, live-table, stage, START, polling or result
queries, including when dbt sets `execute=true` or live checks were requested.
Direct `cortex_eval__render_config` calls default to normal rendering, which
still queries the actual content hash and inventory; `execute_checks=false`
only disables live table validation. Pass `dry_run=true` explicitly for preview.

Preview configs carry `preview.executable: false`, the `preview_unresolved`
dataset-hash sentinel, and `preview.dataset_exists: null`. Dataset creation/reuse
is unknown, so no dataset block is inferred; an explicitly requested inclusion
is only a shape preview, not proof of existence. Under dbt `execute=false`, config
rendering also uses this unresolved preview. Do not upload preview output to
START or treat it as a full executable plan. Normal execution rerenders against
real content and inventory. The separate offline `cortex_eval__execution_plan`
still uses its established dataset token and signed identity/policy contract;
neither preview proves native execution, Agent versions/aliases, or dataset
existence. These are local Jinja regression checks, not live dbt qualification.

## Ground-truth rules

- Every row has one `OUTPUT` VARIANT with `ground_truth_output` for
  `answer_correctness`.
- Tool metrics use `ground_truth_invocations`; expected invocation tool names
  must resolve to declared native-supported Analyst, Cortex Search, `web_search`,
  or generic custom tools on the single deployed Agent.
- `tool_execution_accuracy` should include `tool_input` and `tool_output` when
  behavior matters.
- Web search expected invocations use `tool_name: web_search`.
- Custom metric prompts preserve `{{input}}`, `{{output}}`, `{{ground_truth}}`,
  and `{{tool_info}}` placeholders.
- Skills, MCP, code execution, and other capability tools cannot be claimed as
  native expected-tool coverage. Skills completed in live probes are
  `completed_with_attachment` unless trace or metric evidence proves invocation;
  MCP may remain attached but built-in evaluation does not invoke it. Use separate
  smoke/integration proof.