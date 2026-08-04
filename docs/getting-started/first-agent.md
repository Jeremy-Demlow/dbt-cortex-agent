# Build your first Agent

## 1. Create a governed dependency

Build a semantic-view model with `materialized='semantic_view'`. Analyst tools
resolve the dbt model name through the manifest; do not hardcode a semantic-view
FQN in `semantic_view_model`.

## 2. Create the Agent exposure

Use the minimal exposure in the [configuration model](../guides/configuration-model.md).
Include the semantic-view `ref()` in `depends_on` and use that model's name in
`semantic_view_model`.

## 3. Configure the deployment boundary

```yaml
vars:
  cortex_agent_deploy_target: safe
  cortex_agent_allowed_targets: [safe]
  cortex_agent_allowed_databases: [ANALYTICS_DEV]
  cortex_agent_schema: AGENTS
  cortex_eval_schema: EVAL
```

Bootstrap does not choose a target or allowed database for an adopter. `AGENTS`
and `EVAL` are optional conventions.

## 4. Validate and render

```bash
dbt-cortex-agent doctor --project-dir . --target safe --json
dbt-cortex-agent manifest validate --project-dir . --target safe --agent orders_assistant --json
dbt-cortex-agent agent render --project-dir . --target safe --agent orders_assistant --json
dbt-cortex-agent agent deploy --project-dir . --target safe --agent orders_assistant --allow-target safe --allow-database ANALYTICS_DEV --json
```

All four commands are non-mutating. Continue with [lifecycle](../guides/lifecycle.md)
only after [Snowflake setup](snowflake-setup.md) is complete.