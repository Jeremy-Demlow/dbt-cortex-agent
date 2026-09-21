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
   `<target.database>.<cortex_agent_schema>.EVAL_CONFIG_STAGE`.

Evaluation never creates, deploys, replaces, or otherwise mutates that Agent. The
eval table FQN comes from the resolved dbt model in `cortex_eval_schema`. Dataset names are content-hashed from
the Agent/suite identity so changed ground truth does not silently reuse a stale
Snowflake dataset.

`dbt-cortex-agent eval run` does not create these prerequisites. Its default path
only renders the authoritative plan. `--apply` uploads a generated JSON config,
creates the stage if needed, starts Snowflake Agent Evaluation, and incurs Cortex
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
`--artifact-dir` overrides it. DEFAULT drift makes the result indeterminate.

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
ground-truth refs, metrics, thresholds, regression tolerances, row evidence, and
pre/post DEFAULT version provenance. It contains only single-Agent identity.

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
Baseline acceptance retains these metadata fields but still omits scored rows.
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