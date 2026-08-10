# Evaluations

An optional evaluation suite is a table model with `config.meta.cortex_eval`. dbt owns the
suite, native configuration, same-Agent target identity, metric policy, and public macros.
The Python CLI consumes one dbt-rendered execution plan and adds bounded polling,
retry, durable candidate artifacts, comparison, gates, and accepted baselines.

## Prerequisites and spend boundary

Before a paid CLI run, provide all three prerequisites:

1. the **normally deployed Agent** selected by the enabled exposure and target;
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

## Python client path

Render the plan without spend:

```bash
dbt-cortex-agent eval run --project-dir . --target sandbox \
  --agent orders_assistant --suite core --json
```

Render and preview the normal Agent deployment through the CLI:

```bash
dbt-cortex-agent agent render --project-dir . --target sandbox \
  --agent orders_assistant --json
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant \
  --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

After review, repeat deploy with explicit `--connection`, matching `--database`,
and `--apply`. Evaluation remains a separate optional paid operation and never
calls the Agent deploy/version lifecycle.

After deploying that Agent and materializing/testing the eval model, an approved
paid run uses:

```bash
dbt-cortex-agent eval run --project-dir . --target sandbox \
  --agent orders_assistant --suite core --connection sandbox \
  --database ANALYTICS_DEV --warehouse EVAL_WH \
  --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
```

The CLI parses, calls `cortex_eval__execution_plan`, verifies plan identity and
signature, proves the Agent exists with a DEFAULT version before upload/START,
validates live table rows, records the pre-run DEFAULT Agent version,
starts/polls the evaluation with bounded transient retry, records post-run
provenance, and writes a candidate JSON under `target/dbt_cortex_agent` unless
`--artifact-dir` overrides it. DEFAULT drift makes the result indeterminate.

The default artifact root is resolved relative to `--project-dir`. An applied
run writes
`target/dbt_cortex_agent/candidates/<agent>/<suite>/<run_name>.json`. Accepted
baselines default to
`target/dbt_cortex_agent/baselines/<agent>/<suite>.json`; `--artifact-dir` moves
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

### Migrate known legacy accepted evidence

Use the current dbt-rendered execution plan to migrate a known pre-schema or
schema-v1 accepted baseline without paying for a new evaluation:

```bash
dbt-cortex-agent eval migrate-baseline legacy.json \
  --project-dir . --target sandbox \
  --agent orders_assistant --suite core \
  --baseline-dir target/dbt_cortex_agent/baselines --json
```

The default is preview and writes nothing. Review the target, current metric
contract, thresholds, regression tolerances, ordered refs, suite signature, and
preserved `run_metadata.legacy_migration` provenance. Apply only to the requested
baseline directory:

```bash
dbt-cortex-agent eval migrate-baseline legacy.json \
  --project-dir . --target sandbox \
  --agent orders_assistant --suite core \
  --baseline-dir target/dbt_cortex_agent/baselines --apply
```

An existing target fails closed. `--force` is valid only with `--apply` and must
be an explicit reviewed overwrite decision. Migration accepts only a passing
legacy baseline whose Agent, suite, and complete summary metric set match the
current plan; it never copies legacy policy into schema v2 and never connects to
Snowflake. A historical physical Agent identity ending in `_EVAL` is incompatible
with the single-Agent plan and is rejected rather than silently migrated.

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