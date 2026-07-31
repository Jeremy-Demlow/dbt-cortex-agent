# Progressive features

Keep the first Agent minimal. Add these only after canonical/native-eval renders and
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
    evaluation_supported: true
    description: Searches governed support content. Use for support-policy questions.
```

## Generic procedure tool

```yaml
- name: OpenOrderProcedure
  type: generic
  identifier: TOOLS.OPEN_ORDER_STATUS
  evaluation_supported: true
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
optional framework tooling, and smoke-test skill selection after deployment.

## Alias promotion and rollback

```bash
dbt run-operation cortex_agent__promote_alias --profiles-dir . --target sandbox \
  --args '{"agent_name":"orders_assistant","from_alias":"validated","to_alias":"production","dry_run":true}'

dbt run-operation cortex_agent__rollback_alias --profiles-dir . --target sandbox \
  --args '{"agent_name":"orders_assistant","alias":"production","to_version":"VERSION$1","dry_run":true}'
```

Review dry-run output before applying either operation.
