{{ config(materialized='table', schema='eval') }}

WITH total_revenue AS (
    SELECT
        'What was total order revenue?' AS input_query,
        'Total order revenue was $' || TO_VARCHAR(ROUND(COALESCE(SUM(revenue), 0), 2), 'FM9999999990.00') || '.' AS ground_truth_output,
        ARRAY_CONSTRUCT(
            OBJECT_CONSTRUCT(
                'tool_name', 'OrdersAnalytics',
                'tool_input', 'Calculate total order revenue.',
                'tool_output', 'Semantic view result with total_revenue.'
            )
        ) AS ground_truth_invocations,
        OBJECT_CONSTRUCT(
            'category', 'orders',
            'test_type', 'in_scope',
            'ground_truth_ref', 'total_revenue'
        ) AS custom_criteria
    FROM {{ ref('orders') }}
),

out_of_scope_competitor_inventory AS (
    SELECT
        'How many units does our largest competitor have in inventory?' AS input_query,
        'The Agent should decline because competitor inventory is outside the governed order data.' AS ground_truth_output,
        ARRAY_CONSTRUCT() AS ground_truth_invocations,
        OBJECT_CONSTRUCT(
            'category', 'boundary',
            'test_type', 'out_of_scope',
            'ground_truth_ref', 'out_of_scope_competitor_inventory'
        ) AS custom_criteria
),

negative_future_revenue AS (
    SELECT
        'What will exact order revenue be next year?' AS input_query,
        'The Agent should explain that the available order history cannot determine exact future revenue.' AS ground_truth_output,
        ARRAY_CONSTRUCT() AS ground_truth_invocations,
        OBJECT_CONSTRUCT(
            'category', 'boundary',
            'test_type', 'negative',
            'ground_truth_ref', 'negative_future_revenue'
        ) AS custom_criteria
)

{{ dbt_cortex_agent.cortex_eval__assemble([
    'total_revenue',
    'out_of_scope_competitor_inventory',
    'negative_future_revenue'
]) }}