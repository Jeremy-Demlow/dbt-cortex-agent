{# Compile-only compatibility fixture for an enterprise Agent materialization
   shape. Tests parse this model; CI must never build it. #}
{{
  config(
    materialized='cortex_agent',
    database='EXAMPLE_CLONE' if target.name == 'clone' else target.database,
    schema='EXAMPLE_LAB' if target.name == 'clone' else 'AGENTS',
    alias='ENTERPRISE_COMPATIBILITY_PROBE',
    tags=['enterprise_compatibility', 'compile_only'],
    post_hook=[
      "GRANT USAGE ON AGENT {{ this }} TO ROLE EXAMPLE_AGENT_USER",
      "GRANT MONITOR ON AGENT {{ this }} TO ROLE EXAMPLE_AGENT_OPERATOR",
    ] if target.name != 'clone' else [],
    meta={
      'agent_display_name': 'Enterprise Compatibility Probe',
      'agent_comment': 'Compile-only fixture for the enterprise Agent materialization contract',
      'agent_role': 'EXAMPLE_CLONE_OWNER' if target.name == 'clone' else 'EXAMPLE_AGENT_OWNER',
      'deploy_alias': 'latest',
      'cortex_agent': {
        'enabled': true,
        'skills': [
          {
            'name': 'governed-analytics-sql',
            'source': {
              'type': 'stage',
              'path': '@EXAMPLE_DB.AGENTS.SKILL_STAGE/governed-analytics-sql'
            }
          }
        ]
      }
    }
  )
}}

models:
  orchestration: claude-opus-4-8

orchestration:
  budget:
    seconds: 300
    tokens: 32000

instructions:
  response: |
    Answer analytical questions directly and prefer charts when useful.
  orchestration: |
    {{ enterprise_compatibility_orchestration_instructions() | indent(4) }}
  sample_questions:
    - question: Which account has the highest example usage?

tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: GovernedAnalytics
      description: Query governed example metrics.
  - tool_spec:
      type: cortex_search
      name: DocumentSearch
      description: Search example documentation.
  - tool_spec:
      type: generic
      name: ScheduleReport
      description: Schedule a reviewed example report.
      input_schema:
        type: object
        properties:
          question:
            type: string
        required: [question]
  - tool_spec:
      type: web_search
      name: Web Search
  - tool_spec:
      type: code_execution
      name: code_execution

tool_resources:
  GovernedAnalytics:
    semantic_view: EXAMPLE_DB.SEMANTIC.EXAMPLE_SEMANTIC_VIEW
    execution_environment:
      type: warehouse
      warehouse: EXAMPLE_WH
      query_timeout: 120
  DocumentSearch:
    search_service: EXAMPLE_DB.DOCS.EXAMPLE_SEARCH
    max_results: 5
  ScheduleReport:
    type: procedure
    identifier: EXAMPLE_DB.AGENTS.SCHEDULE_REPORT
    name: SCHEDULE_REPORT(VARCHAR)
    execution_environment:
      type: warehouse
      warehouse: EXAMPLE_WH
  Web Search:
    max_results: 10
  code_execution: {}

mcp_servers:
  - server_spec:
      name: EXAMPLE_DB.MCP.EXAMPLE_SERVER

skills:
  - name: governed-analytics-sql
    source:
      type: STAGE
      path: "@EXAMPLE_DB.AGENTS.SKILL_STAGE/governed-analytics-sql"