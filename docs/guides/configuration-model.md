# Configuration model

dbt metadata is authoritative. The CLI runs `dbt parse` and consumes the resolved
`target/manifest.json`; it does not parse source YAML into a second model.

## Agent exposure

Store Agent metadata at `exposures[].config.meta.cortex_agent`:

```yaml
version: 2
exposures:
  - name: orders_assistant
    type: application
    maturity: medium
    owner:
      name: analytics
      email: analytics@example.com
    depends_on:
      - ref('sem_orders')
    config:
      meta:
        cortex_agent:
          enabled: true
          snowflake_name: ORDERS_ASSISTANT
          naming:
            sandbox: ORDERS_ASSISTANT_SANDBOX
          access:
            usage_roles: [ORDERS_AGENT_USER]
          instructions:
            orchestration: Use OrdersAnalytics for governed order questions.
            response: Answer concisely and state the requested time scope.
          tools:
            - name: OrdersAnalytics
              type: cortex_analyst_text_to_sql
              semantic_view_model: sem_orders
              description: Analyzes governed order revenue and volume.
```

`depends_on` creates dbt lineage. `semantic_view_model` is a dbt model name and
must resolve uniquely to a `semantic_view` relation. See the full
[Agent metadata reference](../reference/agent-metadata.md).

## Evaluation model

Store suite metadata at `models[].config.meta.cortex_eval` on a table model:

```yaml
version: 2
models:
  - name: eval_orders_assistant__core
    config:
      materialized: table
      meta:
        cortex_eval:
          name: core
          agent: orders_assistant
          projection: native_eval
          metrics: [answer_correctness, tool_selection_accuracy]
          thresholds:
            answer_correctness: 0.8
          regression_tolerances:
            answer_correctness: 0.01
          questions:
            - id: revenue_last_month
              test_type: in_scope
              expected_tools: [OrdersAnalytics]
              ground_truth_ref: revenue_last_month
```

The table must expose `INPUT_QUERY` and one `OUTPUT` VARIANT containing
`ground_truth_output`, `ground_truth_invocations`, and stable custom criteria.
See [eval metadata](../reference/eval-metadata.md).

## dbt variables

Set project policy in the consumer `dbt_project.yml`:

```yaml
vars:
  cortex_agent_deploy_target: sandbox
  cortex_agent_allowed_targets: [sandbox]
  cortex_agent_allowed_databases: [ANALYTICS_DEV]
  cortex_agent_schema: AGENTS
  cortex_eval_schema: EVAL
  cortex_agent_skill_stage: SKILL_STAGE
```

The deploy target defaults internally to `dbt_focus` for backward compatibility,
but adoption must set it explicitly. The allowed-target list defaults to the
deploy target; the allowed-database list defaults empty and blocks mutation.
Schemas and the skill stage name are conventions, not grants or object creation.
Native evaluation uses `<target.database>.<cortex_agent_schema>.EVAL_CONFIG_STAGE`.
See
[variables](../reference/variables.md).

## CLI flags and environment precedence

Configuration precedence is **CLI option > environment variable > built-in
default**. Source metadata and dbt vars are not overridden by similarly named CLI
flags; CLI flags select execution context and enforce an additional safety layer.

| CLI option | Environment | Built-in default |
|---|---|---|
| `--project-dir` | `DBT_PROJECT_DIR` | current directory |
| `--manifest` | `DBT_MANIFEST` | `target/manifest.json` under project |
| `--target` | `DBT_TARGET` | unset |
| `--connection` | `SNOWFLAKE_CONNECTION_NAME` | unset; apply still requires the CLI flag |
| `--database` | `SNOWFLAKE_DATABASE` | unset |
| `--schema` | `SNOWFLAKE_SCHEMA` | unset |
| `--warehouse` | `SNOWFLAKE_WAREHOUSE` | unset |
| `--artifact-dir` | `DBT_CORTEX_AGENT_ARTIFACT_DIR` | `target/dbt_cortex_agent` |
| `--dbt-executable` | `DBT_EXECUTABLE` | `dbt` |
| `--snow-executable` | `SNOW_EXECUTABLE` | `snow` |

`--allow-target` and `--allow-database` are repeatable command-local gates and
have no environment fallback. `--no-parse` is only for controlled test fixtures;
normal manifest-dependent operations always parse first. See [CLI reference](../reference/cli.md).