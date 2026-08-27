{{ config(
    materialized='table',
    database=env_var('CORTEX_AGENT_LIVE_DATABASE_EVAL', 'DBT_CORTEX_AGENT_SANDBOX_EVAL'),
    schema='eval'
) }}

SELECT
    'What was total order revenue?' AS input_query,
    OBJECT_CONSTRUCT(
        'ground_truth_output',
        'Use OrdersAnalytics and return total revenue.',
        'custom_criteria',
        OBJECT_CONSTRUCT(
            'test_type', 'in_scope',
            'ground_truth_ref', 'live_total_revenue'
        )
    ) AS output