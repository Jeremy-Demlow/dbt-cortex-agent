{{ config(
    materialized='semantic_view',
    database=env_var('CORTEX_AGENT_LIVE_DATABASE_A', 'DBT_CORTEX_AGENT_SANDBOX_A'),
    schema='semantic'
) }}

TABLES (
    orders AS {{ ref('orders') }}
      PRIMARY KEY (order_id)
      COMMENT = 'Synthetic orders for protected live proof'
)

FACTS (
    orders.revenue AS revenue
      COMMENT = 'Revenue recorded for the order'
)

DIMENSIONS (
    orders.order_date AS order_date
      COMMENT = 'Date the order was completed',
    orders.region AS region
      COMMENT = 'Region credited with the order'
)

METRICS (
    orders.total_revenue AS SUM(orders.revenue)
      COMMENT = 'Total order revenue'
)

COMMENT = 'Protected multi-database proof semantic view'