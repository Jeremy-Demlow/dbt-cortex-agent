# Build your first Agent

## Guided Cortex Code path

The project-local
[`dbt-cortex-agent-project` skill](../../.cortex/skills/dbt-cortex-agent-project/SKILL.md)
guides this workflow for a new or existing dbt project. It begins with read-only
discovery and objective/levers/data/proof, supports an existing semantic view,
the fixed Orders starter, or migration of an existing Agent, and can add eval
authoring when ground truth exists. It uses stable 0.0.3 commands, shows manual
command parity, and requires distinct approvals for local writes, Snowflake
mutation/runtime, paid evaluation, and baseline movement.

The skill is checked into this repository for project use. It is script-free and
is not published or installed globally by the package.

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