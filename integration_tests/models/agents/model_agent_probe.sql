{{
  config(
    materialized='cortex_agent',
    database=target.database,
    schema='AGENTS',
    alias='MODEL_AGENT_PROBE',
    meta={
      'agent_display_name': 'Model Agent Probe',
      'agent_comment': 'Compile-only full-body Cortex Agent model',
      'deploy_alias': 'latest',
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
    Answer concisely from governed tools.
  orchestration: |
    Use OrdersAnalytics for order questions.

tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: OrdersAnalytics
      description: Query governed order metrics.

tool_resources:
  OrdersAnalytics:
    semantic_view: DUMMY.SEMANTIC.SEM_ORDERS
    execution_environment:
      type: warehouse
      warehouse: DUMMY
      query_timeout: 60