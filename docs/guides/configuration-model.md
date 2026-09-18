# Configuration model

dbt is authoritative. A Cortex Agent is a model with
`materialized='cortex_agent'`; the model body is the native Agent YAML
specification. Python reads operational metadata from `target/manifest.json`
for skills, runtime, and evaluations, but never reparses the model source.

## Full-body Agent model

```jinja
{% do ref('sem_orders') %}
{{
  config(
    materialized='cortex_agent',
    database=target.database,
    schema='AGENTS',
    alias='ORDERS_ASSISTANT',
    meta={
      'agent_display_name': 'Orders Assistant',
      'deploy_alias': 'latest',
      'cortex_agent': {
        'enabled': true,
        'evaluation': {'native_tools': ['OrdersAnalytics']}
      }
    }
  )
}}

models:
  orchestration: claude-sonnet-4-6

instructions:
  orchestration: Use OrdersAnalytics for governed order questions.
  response: Answer concisely and state the requested time scope.

tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: OrdersAnalytics
      description: Analyzes governed order revenue and volume.

tool_resources:
  OrdersAnalytics:
    semantic_view: "{{ target.database }}.SEMANTIC.SEM_ORDERS"
    execution_environment:
      type: warehouse
      warehouse: "{{ target.warehouse }}"
      query_timeout: 60
```

Every model must explicitly declare `models.orchestration`. Values such as
`claude-sonnet-4-6`, `claude-opus-4-6`, or `auto` are preserved unchanged;
missing orchestration fails compilation.

Use no-output `ref()` calls for Agent dependencies. The relation database,
schema, and alias are the physical Agent identity. `config.meta.cortex_agent`
contains operational metadata that is not part of the deployed specification:
explicit local skill mapping and native-evaluation classifications. Local uploads
require `config.meta.cortex_agent.skills` matching native top-level `skills`;
compiled YAML is comparison evidence, not a fallback upload contract. See
[skills](skills.md). Grants remain adopter-owned.

Preview the Agent with dbt, then use the package-native deployment workflow:

```bash
dbt compile --select orders_assistant  # non-mutating preview
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant \
  --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

Direct `dbt build --select orders_assistant` is the lower-level immutable deploy
primitive. It is appropriate only when the operator separately owns skill
upload, execution context, allowlist, and evidence sequencing.

The materialization uses the invoking dbt role and never switches session roles.
`meta.agent_role` does not select a deployment role. Configure the approved role
in the dbt profile/CLI execution context instead. User-authored hooks are separate
adopter code; they do not make Agent DDL transactional or provide automatic
rollback. Compilation writes local artifacts and may open an adapter connection;
non-mutating does not mean offline.

## Optional evaluation model

Suite metadata remains at `models[].config.meta.cortex_eval` on a table model:

```yaml
version: 2
models:
  - name: orders_assistant_core
    config:
      materialized: table
      meta:
        cortex_eval:
          name: core
          agent: orders_assistant
          metrics: [answer_correctness, tool_selection_accuracy]
          thresholds:
            answer_correctness: 0.8
          questions:
            - id: revenue_last_month
              test_type: in_scope
              expected_tools: [OrdersAnalytics]
              ground_truth_ref: revenue_last_month
```

The optional table evaluates the same physical Agent and never creates another
Agent. It exposes `INPUT_QUERY` and an `OUTPUT` VARIANT containing ground truth,
expected invocations, and stable criteria.

## dbt variables

```yaml
vars:
  cortex_agent_deploy_target: sandbox
  cortex_agent_allowed_targets: [sandbox]
  cortex_agent_allowed_databases: [ANALYTICS_DEV]
  cortex_agent_schema: AGENTS
  cortex_eval_schema: EVAL
```

The allowed-database list defaults empty and blocks mutation. Built-in
evaluation uses `<target.database>.<cortex_agent_schema>.EVAL_CONFIG_STAGE`.