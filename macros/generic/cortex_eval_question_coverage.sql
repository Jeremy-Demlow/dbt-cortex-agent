{% test cortex_eval_question_coverage(model, expected_refs=[], expected_tools=[], min_out_of_scope=0, min_negative=0) %}
  {# Suite authoring contract (REQ-030). Fails (returns rows) when:
     - any expected ground_truth_ref is not present exactly once, OR
     - the suite has fewer than min_out_of_scope out_of_scope rows, OR
     - the suite has fewer than min_negative negative rows, OR
     - any expected tool is not covered by >=1 in-scope question's expected invocations.
     test_type defaults to 'in_scope' when absent. #}
  {% set expected_rows = [] %}
  {% for ref in expected_refs %}
    {% do expected_rows.append("SELECT '" ~ (ref | replace("'", "''")) ~ "' AS ground_truth_ref") %}
  {% endfor %}

  {% set tool_rows = [] %}
  {% for tool in expected_tools %}
    {% do tool_rows.append("SELECT '" ~ (tool | replace("'", "''")) ~ "' AS tool_name") %}
  {% endfor %}

  WITH actual AS (
    SELECT
      output:custom_criteria:ground_truth_ref::STRING AS ground_truth_ref,
      COALESCE(output:custom_criteria:test_type::STRING, 'in_scope') AS test_type,
      output:ground_truth_invocations AS ground_truth_invocations
    FROM {{ model }}
  ),

  {# 1) Per-ref coverage: each expected ref must map to exactly one row. #}
  {% if expected_rows | length > 0 %}
  expected AS (
    {{ expected_rows | join('\nUNION ALL\n') }}
  ),
  ref_violations AS (
    SELECT
      e.ground_truth_ref AS detail,
      'ref_not_exactly_once' AS violation
    FROM expected e
    LEFT JOIN actual a ON a.ground_truth_ref = e.ground_truth_ref
    GROUP BY e.ground_truth_ref
    HAVING COUNT(a.ground_truth_ref) != 1
  ),
  {% else %}
  ref_violations AS (SELECT NULL AS detail, NULL AS violation WHERE 1=0),
  {% endif %}

  {# 2) Distribution minimums for boundary rows. #}
  distribution_violations AS (
    SELECT 'out_of_scope' AS detail, 'below_min_out_of_scope' AS violation
    FROM actual
    HAVING COUNT_IF(test_type = 'out_of_scope') < {{ min_out_of_scope }}
    UNION ALL
    SELECT 'negative' AS detail, 'below_min_negative' AS violation
    FROM actual
    HAVING COUNT_IF(test_type = 'negative') < {{ min_negative }}
  ),

  {# 3) Tool coverage: every expected tool named by >=1 in-scope row's invocations. #}
  {% if tool_rows | length > 0 %}
  expected_tools AS (
    {{ tool_rows | join('\nUNION ALL\n') }}
  ),
  covered_tools AS (
    SELECT DISTINCT f.value:tool_name::STRING AS tool_name
    FROM actual a,
      LATERAL FLATTEN(input => a.ground_truth_invocations) f
    WHERE a.test_type = 'in_scope'
  ),
  tool_violations AS (
    SELECT et.tool_name AS detail, 'tool_not_covered' AS violation
    FROM expected_tools et
    LEFT JOIN covered_tools ct ON ct.tool_name = et.tool_name
    WHERE ct.tool_name IS NULL
  ),
  {% else %}
  tool_violations AS (SELECT NULL AS detail, NULL AS violation WHERE 1=0),
  {% endif %}

  all_violations AS (
    SELECT detail, violation FROM ref_violations
    UNION ALL
    SELECT detail, violation FROM distribution_violations
    UNION ALL
    SELECT detail, violation FROM tool_violations
  )

  SELECT * FROM all_violations
{% endtest %}
