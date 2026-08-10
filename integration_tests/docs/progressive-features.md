# Progressive features

Keep the first Agent minimal. Add these only after the full Agent render and
the guarded lifecycle are understood.

## Cortex Search tool

Add the pre-existing service as an exposure dependency and tool:

```yaml
depends_on:
  - ref('sem_orders')
  - "{{ source('search', 'support_search_service') }}"
tools:
  - name: SupportSearch
    type: cortex_search
    search_service: SUPPORT.SEARCH.SUPPORT_SEARCH_SERVICE
    description: Searches governed support content. Use for support-policy questions.
```

## Generic procedure tool

```yaml
- name: OpenOrderProcedure
  type: generic
  identifier: TOOLS.OPEN_ORDER_STATUS
  description: Returns status for a supplied order identifier.
```

The procedure must already exist and its privileges are managed separately.

## Web search

```yaml
capabilities:
  web_search:
    enabled: true
    max_results: 5
```

Use only for questions that genuinely require public web information.

## Skill

```yaml
capabilities:
  skills:
    - name: order_summary
      source:
        type: stage
        path: "@{{ target.database }}.{{ var('cortex_agent_schema','AGENTS') }}.{{ var('cortex_agent_skill_stage','SKILL_STAGE') }}/agents/orders_assistant/order_summary"
```

Place local content at
`models/agents/orders_assistant/skills/order_summary/SKILL.md`, upload it with the
installed CLI, and smoke-test skill selection after deployment:

```bash
dbt-cortex-agent skill plan --project-dir . --target sandbox \
  --agent orders_assistant --json
dbt-cortex-agent skill upload --project-dir . --target sandbox \
  --agent orders_assistant --json
```

## Alias promotion and rollback

```bash
dbt-cortex-agent agent promote --project-dir . --target sandbox \
  --agent orders_assistant --from-alias validated --to-alias production \
  --allow-target sandbox --allow-database AM_SKI_RESORT_DBT_FOCUS
dbt-cortex-agent agent rollback --project-dir . --target sandbox \
  --agent orders_assistant --alias production --to-version 'VERSION$1' \
  --allow-target sandbox --allow-database AM_SKI_RESORT_DBT_FOCUS
```

Review dry-run output before applying either operation.
