{% do ref('sem_orders_live') %}
{{
  config(
    materialized='cortex_agent',
    database=env_var('CORTEX_AGENT_LIVE_DATABASE_A', 'DBT_CORTEX_AGENT_SANDBOX_A'),
    schema='AGENTS',
    alias='SHARED_ASSISTANT',
    meta={'deploy_alias': 'latest', 'cortex_agent': {'enabled': true}}
  )
}}

models:
  orchestration: claude-sonnet-4-6

instructions:
  orchestration: Use OrdersAnalytics for governed order questions.
  response: Answer concisely and state units. Proof revision {{ env_var('CORTEX_AGENT_LIVE_SPEC_REVISION', 'v1') }}.

tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: OrdersAnalytics
      description: Query synthetic governed order metrics.

tool_resources:
  OrdersAnalytics:
    semantic_view: "{{ env_var('CORTEX_AGENT_LIVE_DATABASE_A', 'DBT_CORTEX_AGENT_SANDBOX_A') }}.SEMANTIC.SEM_ORDERS_LIVE"
    execution_environment:
      type: warehouse
      warehouse: "{{ target.warehouse }}"
      query_timeout: 60