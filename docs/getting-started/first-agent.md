# Build your first Agent

## Scaffold with the shipped CLI

Preview the smallest generic Agent without writing files:

```bash
dbt-cortex-agent agent scaffold --project-dir . \
  --agent orders_assistant --json
```

After reviewing the proposed paths, add `--apply`. A Semantic View is optional;
use `--semantic-view-model sem_orders` only when that governed model already
exists. Use `--with-eval` only when representative questions and SQL-computed
ground truth are ready.

The repository-local
[`dbt-cortex-agent-project` skill](../../.cortex/skills/dbt-cortex-agent-project/SKILL.md)
can guide maintainers through the same workflow, but it is not published or
required by the package. Direct CLI commands are the adopter interface.

## 1. Create a governed dependency

Build a semantic-view model with `materialized='semantic_view'`. Analyst tools
resolve the dbt model name through the manifest; do not hardcode a semantic-view
FQN in `semantic_view_model`.

## 2. Create the full-body Agent model

Use the model in the [configuration model](../guides/configuration-model.md).
Configure `materialized='cortex_agent'`, use a no-output `ref()` for each governed
dependency, and put the native Agent YAML in the model body. The model relation
supplies the physical Agent name.

At this point the project has an Agent-only path. Evaluation metadata and an eval
table are optional and do not change the Agent specification or deployment.

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

## 4. Validate and compile

```bash
dbt-cortex-agent doctor --project-dir . --target safe --json
dbt-cortex-agent manifest validate --project-dir . --target safe --agent orders_assistant --json
dbt compile --project-dir . --profiles-dir . --target safe --select orders_assistant
```

These commands are non-mutating. Continue with [lifecycle](../guides/lifecycle.md)
only after [Snowflake setup](snowflake-setup.md) is complete.