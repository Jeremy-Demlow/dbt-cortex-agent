# Build your first Agent

## 1. Create a governed dependency

Build a semantic-view model with `materialized='semantic_view'`. Agent Analyst
tools resolve the model name through the dbt manifest; hardcoded semantic-view FQNs
are not needed.

## 2. Create the Agent exposure

Use the minimal exposure from the [package README](../../README.md#first-agent).
Include the semantic-view `ref()` in `depends_on` and the same model name in
`semantic_view_model`.

## 3. Configure the sandbox boundary

```yaml
# consuming dbt_project.yml
vars:
  cortex_agent_deploy_target: sandbox
  cortex_agent_schema: AGENTS
  cortex_eval_schema: EVAL
```

## 4. Validate and render

```bash
dbt deps
dbt parse
dbt run-operation cortex_agent__validate \
  --args '{"agent_name":"orders_assistant","projection":"canonical"}'
dbt run-operation cortex_agent__render_spec \
  --args '{"agent_name":"orders_assistant","projection":"canonical"}'
dbt run-operation cortex_agent__deploy \
  --args '{"agent_name":"orders_assistant","projection":"canonical","dry_run":true}'
```

## 5. Deploy deliberately

```bash
dbt run-operation cortex_agent__deploy --target sandbox \
  --args '{"agent_name":"orders_assistant","projection":"canonical","dry_run":false}'
```

An unchanged spec and unchanged staged skills skip version churn.
