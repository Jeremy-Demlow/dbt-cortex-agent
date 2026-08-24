{{ config(
    materialized='table',
    database=env_var('CORTEX_AGENT_LIVE_DATABASE_EVAL'),
    schema='eval'
) }}

SELECT
    'What was total order revenue?' AS input_query,
    OBJECT_CONSTRUCT(
        'ground_truth_output',
        'Use OrdersAnalytics and return total revenue.',
        'ground_truth_invocations',
        ARRAY_CONSTRUCT(OBJECT_CONSTRUCT('tool_name', 'OrdersAnalytics')),
        'custom_criteria',
        OBJECT_CONSTRUCT(
            'test_type', 'in_scope',
            'ground_truth_ref', 'live_total_revenue'
        )
    ) AS output