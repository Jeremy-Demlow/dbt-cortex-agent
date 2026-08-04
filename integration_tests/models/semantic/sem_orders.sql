{{ config(materialized='semantic_view') }}

TABLES (
    orders AS {{ ref('orders') }}
      PRIMARY KEY (order_id)
      WITH SYNONYMS ('sales orders')
      COMMENT = 'Completed customer orders'
)

FACTS (
    orders.revenue AS revenue
      COMMENT = 'Revenue recorded for the order'
)

DIMENSIONS (
    orders.order_date AS order_date
      WITH SYNONYMS ('sale date')
      COMMENT = 'Date the order was completed',
    orders.region AS region
      WITH SYNONYMS ('sales region')
      COMMENT = 'Region credited with the order'
)

METRICS (
    orders.total_revenue AS SUM(orders.revenue)
      WITH SYNONYMS ('sales', 'revenue')
      COMMENT = 'Total order revenue',
    orders.total_orders AS COUNT(orders.order_id)
      WITH SYNONYMS ('order count')
      COMMENT = 'Number of completed orders',
    orders.average_order_value AS AVG(orders.revenue)
      WITH SYNONYMS ('average sale')
      COMMENT = 'Average revenue per order'
)

COMMENT = 'Starter semantic view for governed order analysis'

AI_SQL_GENERATION 'Use only the declared dimensions and metrics. Use order_date for time filters and region for geographic comparisons.'

AI_QUESTION_CATEGORIZATION 'Accept questions about order revenue, count, average value, dates, and regions. Reject unrelated operational or competitor questions.'
