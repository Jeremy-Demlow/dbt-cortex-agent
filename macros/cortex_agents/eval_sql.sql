{% macro cortex_eval__current_season_cte(date_relation) %}
current_season AS (
    SELECT ski_season
    FROM {{ date_relation }}
    WHERE full_date = CURRENT_DATE()
)
{% endmacro %}

{% macro cortex_eval__last_complete_season_cte(date_relation) %}
most_recent_complete AS (
    SELECT MAX(ski_season) AS ski_season
    FROM {{ date_relation }}
    WHERE ski_season < (SELECT ski_season FROM current_season)
)
{% endmacro %}

{% macro cortex_eval__row(question_cte) %}
SELECT
    input_query,
    OBJECT_CONSTRUCT(
        'ground_truth_output', ground_truth_output,
        'ground_truth_invocations', ground_truth_invocations,
        'custom_criteria', custom_criteria
    )::VARIANT AS output
FROM {{ question_cte }}
{% endmacro %}

{% macro cortex_eval__assemble(question_ctes) %}
  {% set rows = [] %}
  {% for question_cte in question_ctes %}
    {% do rows.append(dbt_cortex_agent.cortex_eval__row(question_cte) | trim) %}
  {% endfor %}
  {{ return(rows | join('\nUNION ALL\n')) }}
{% endmacro %}
