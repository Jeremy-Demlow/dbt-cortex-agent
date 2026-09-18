# Agent model and metadata reference

An Agent is a dbt model with `materialized='cortex_agent'`. The model relation
defines its physical Snowflake identity, the compiled model body is the native
Agent specification, and `config.meta` carries lifecycle metadata that is not
part of that specification.

The package discovers Agents from a fresh `target/manifest.json`. Directory
layout is a convention and legacy dbt exposures are not a public Agent contract.

## Minimal model

```jinja
{{
  config(
    materialized='cortex_agent',
    database=target.database,
    schema=var('cortex_agent_schema', 'AGENTS'),
    alias='ORDERS_ASSISTANT',
    meta={
      'agent_display_name': 'Orders Assistant',
      'agent_comment': 'Managed by dbt-cortex-agent',
      'deploy_alias': target.name,
      'cortex_agent': {'enabled': true}
    }
  )
}}

models:
  orchestration: claude-sonnet-4-6

orchestration:
  budget:
    seconds: 60
    tokens: 16000

instructions:
  response: |
    Answer only from configured capabilities and state material assumptions.
```

Every compiled body must be a YAML mapping and explicitly define
`models.orchestration`. The materialization preserves the remaining native
Agent fields rather than translating them through a package-specific schema.

## Identity and discovery

| Contract | Source |
|---|---|
| Logical Agent name | dbt model `name` |
| Physical database | compiled model `database` |
| Physical schema | compiled model `schema` |
| Physical object name | compiled model `alias`, falling back to model name |
| Physical FQN | `database.schema.alias` resolved from the manifest |
| Enabled discovery | `meta.cortex_agent.enabled`, default true for a `cortex_agent` model |
| Dependency graph | no-output `ref()` calls in the model |
| Native specification | compiled model body |

Logical Agent names and physical FQNs must each be unique in one target-resolved
manifest. Python consumes compiled manifest values and does not infer identity
from `models/agents/...` paths.

## Lifecycle metadata

These top-level `config.meta` keys control the materialization and are not added
to the Agent specification:

| Field | Type | Default | Behavior |
|---|---|---|---|
| `agent_display_name` | string | physical object name | Sets the Agent profile display name. |
| `agent_comment` | string | `Managed by dbt-cortex-agent` | Sets the Snowflake object comment. |
| `deploy_alias` | string | current dbt target | Alias reconciled to the managed content version. |

`agent_role` is not consumed by the materialization and does not switch roles.
The approved invoking dbt role is authoritative. There is no automatic grant
contract for historical `access` metadata; grants are adopter-managed.

`meta.cortex_agent` carries package coordination metadata:

| Field | Type | Behavior |
|---|---|---|
| `enabled` | boolean | Set false to exclude the model from package discovery. |
| `skills` | list | Required for local uploads and stage-skill smoke discovery; resolved name/source type/path declarations must match native top-level `skills`. No compiled-spec fallback. |
| `evaluation` | mapping | Optional evaluation capability classifications used by package validation. |

The native Agent body remains authoritative for models, orchestration,
instructions, sample questions, tools, tool resources, skills, and arbitrary
supported or experimental specification mappings.

Fresh parse need not contain compiled model bodies. Put local skill declarations
in `config.meta.cortex_agent.skills` even when the model body also declares them.
Readable manifest YAML/JSON is compared against metadata; Python does not render
Jinja. See [skills](../guides/skills.md) for examples and detection limitations.

## Dependencies and tools

Use no-output `ref()` calls to put governed dependencies in the dbt graph:

```jinja
{% do ref('sem_orders') %}
{% do ref('orders_policy_search') %}
```

Then author native tool and resource mappings in the body:

```yaml
tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: OrdersAnalytics
      description: Answers governed order questions.

tool_resources:
  OrdersAnalytics:
    semantic_view: "{{ target.database }}.SEMANTIC.SEM_ORDERS"
    execution_environment:
      type: warehouse
      warehouse: "{{ target.warehouse }}"
      query_timeout: 60
```

The package does not require a Semantic View. Cortex Search, native tools,
skills, and experimental mappings are optional additions governed by the native
Agent specification and their own infrastructure prerequisites.

## Render and deploy

```bash
dbt compile --project-dir . --target sandbox --select orders_assistant
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant \
  --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

Compile is the non-mutating specification preview. Package-native deploy is the
recommended complete workflow; its applied path uploads declared skills and
delegates dependency-aware Agent mutation to dbt. See the
[configuration model](../guides/configuration-model.md) and
[lifecycle guide](../guides/lifecycle.md).