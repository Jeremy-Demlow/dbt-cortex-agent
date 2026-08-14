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
        'access': {'usage_roles': ['ORDERS_AGENT_USER']},
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
access hints, local skill mapping, and native-evaluation classifications.

Build the Agent with:

```bash
dbt compile --select orders_assistant  # non-mutating preview
dbt build --select orders_assistant    # immutable deploy
```

When `meta.agent_role` is set, the materialization switches to that role for
Agent lifecycle statements and post-hooks, then restores the original role on
successful completion. dbt/Jinja materializations do not provide `try/finally`;
if a statement or hook raises after `USE ROLE`, discard that failed dbt process
instead of reusing its thread/session.

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

## Legacy exposures

Enabled `exposures[].config.meta.cortex_agent` declarations remain readable for
migration compatibility. New projects should use full-body models. Model Agents
cannot be deployed through the legacy Python `agent render/deploy` commands.

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