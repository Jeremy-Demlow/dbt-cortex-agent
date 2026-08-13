{% do ref('sem_orders') %}
{{
  config(
    materialized='cortex_agent',
    database=target.database,
    schema='AGENTS',
    alias='ORDERS_ASSISTANT_SANDBOX',
    meta={
      'agent_display_name': 'Orders Assistant',
      'agent_comment': 'Governed order analytics assistant',
      'deploy_alias': 'latest',
      'cortex_agent': {
        'enabled': true,
        'access': {
          'usage_roles': [env_var('CORTEX_AGENT_RUNTIME_ROLE', 'ORDERS_AGENT_USER')],
          'monitor_roles': [env_var('CORTEX_AGENT_MONITOR_ROLE', 'ORDERS_AGENT_MONITOR')]
        },
        'evaluation': {'native_tools': ['OrdersAnalytics']}
      }
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
  orchestration: Use OrdersAnalytics for governed order questions. Do not invent unavailable facts.
  response: Answer concisely and state the requested time scope and units.
  sample_questions:
    - question: What was total order revenue?
    - question: Which region generated the most revenue?

tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: OrdersAnalytics
      description: |
        Analyzes governed order revenue, count, average value, dates, and regions.
        Use for aggregate order questions and comparisons. Not for competitor data,
        inventory, support tickets, or forecasts.

tool_resources:
  OrdersAnalytics:
    semantic_view: "{{ target.database }}.SEMANTIC.SEM_ORDERS"
    execution_environment:
      type: warehouse
      warehouse: "{{ target.warehouse }}"
      query_timeout: 60
