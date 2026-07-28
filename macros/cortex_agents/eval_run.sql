{% macro cortex_eval__config_filename(model_name) %}
  {# Stable within a dbt invocation; matches the filename cortex_eval__start
     uploads so STATUS polling can find the same staged config. #}
  {% set invocation_slug = invocation_id | replace('-', '') %}
  {{ return(model_name ~ '_' ~ invocation_slug ~ '.yaml') }}
{% endmacro %}

{% macro cortex_eval__results_fqn(run_name) %}
  {% set safe = modules.re.sub('[^0-9A-Za-z_]', '_', run_name) | upper %}
  {{ return(target.database ~ '.' ~ cortex_eval__schema() ~ '.EVAL_RESULTS_' ~ safe) }}
{% endmacro %}

{% macro cortex_eval__status(run_name, config_url) %}
  {# One STATUS call. Returns the uppercased STATUS column, or '' when absent. #}
  {% if not execute %}
    {{ return('') }}
  {% endif %}
  {% set results = run_query("CALL EXECUTE_AI_EVALUATION('STATUS', OBJECT_CONSTRUCT('run_name', '" ~ run_name ~ "'), '" ~ config_url ~ "')") %}
  {% if results.rows | length == 0 %}
    {{ return('') }}
  {% endif %}
  {% set col_names = results.column_names | map('upper') | list %}
  {% if 'STATUS' in col_names %}
    {{ return(results.rows[0][col_names.index('STATUS')] | string | upper) }}
  {% endif %}
  {{ return(results.rows[0][0] | string | upper) }}
{% endmacro %}

{% macro cortex_eval__poll(run_name, config_url, max_attempts=60, interval=15) %}
  {# Poll EXECUTE_AI_EVALUATION STATUS until a terminal state, sleeping between
     attempts via server-side SYSTEM$WAIT (Jinja has no sleep). Exact-match on
     terminal tokens: INVOCATION_COMPLETED is NOT terminal (metric judge still
     running), so substring-matching COMPLETED would exit a phase too early. #}
  {% set terminal_ok = ['COMPLETED', 'SUCCEEDED', 'DONE'] %}
  {% set terminal_fail = ['FAILED', 'ERROR', 'CANCELLED', 'INVOCATION_FAILED', 'INVOCATION_ERROR'] %}
  {% if not execute %}
    {{ return('DRY') }}
  {% endif %}
  {% for attempt in range(1, max_attempts + 1) %}
    {% set status = cortex_eval__status(run_name, config_url) %}
    {% do log("  [" ~ attempt ~ "/" ~ max_attempts ~ "] " ~ run_name ~ " status=" ~ status, info=True) %}
    {% if status in terminal_ok %}
      {{ return('COMPLETED') }}
    {% endif %}
    {% if status in terminal_fail %}
      {{ return('FAILED: ' ~ status) }}
    {% endif %}
    {% do run_query("CALL SYSTEM$WAIT(" ~ interval ~ ")") %}
  {% endfor %}
  {{ return('TIMEOUT') }}
{% endmacro %}

{% macro cortex_eval__results(model_name, run_name, projection='native_eval') %}
  {# Materialize the run's metric rows into a real EVAL table, stamped with a
     run_metadata VARIANT (evaluated DEFAULT version, alias map, spec hash,
     dataset FQN, account, git sha, invocation) for auditability. #}
  {% set eval_meta = cortex_eval__get_eval_meta(model_name) %}
  {% set exposure = cortex_agent__get_agent(eval_meta.get('agent')) %}
  {% set agent = exposure.meta.get('cortex_agent', {}) %}
  {% set agent_fqn = cortex_agent__target_agent_fqn(agent, projection) %}
  {% set parts = agent_fqn.split('.') %}
  {% set aliases = cortex_agent__describe_aliases(agent_fqn) %}
  {% set evaluated_version = aliases.get('DEFAULT', '') %}
  {% set spec_hash = cortex_agent__current_spec_hash(agent_fqn) or '' %}
  {% set dataset_fqn = cortex_eval__dataset_fqn(model_name) %}
  {% set git_sha = env_var('GITHUB_SHA', env_var('DBT_GIT_SHA', '')) %}
  {% set results_fqn = cortex_eval__results_fqn(run_name) %}

  {# Fail-closed: this primitive creates a table, so guard it directly. #}
  {% if execute %}
    {% do cortex_agent__assert_deploy_target('cortex_eval__results') %}
  {% endif %}

  {# Escape single quotes in interpolated string literals to keep the CTAS safe. #}
  {% set q_run_name = run_name | replace("'", "''") %}
  {% set q_git_sha = git_sha | replace("'", "''") %}

  {% set metadata_sql %}
    OBJECT_CONSTRUCT(
      'run_name', '{{ q_run_name }}',
      'agent_fqn', '{{ agent_fqn }}',
      'projection', '{{ projection }}',
      'evaluated_version', '{{ evaluated_version }}',
      'aliases', PARSE_JSON('{{ tojson(aliases) }}'),
      'spec_md5', '{{ spec_hash }}',
      'dataset_fqn', '{{ dataset_fqn }}',
      'account', CURRENT_ACCOUNT(),
      'git_sha', '{{ q_git_sha }}',
      'invocation_id', '{{ invocation_id }}',
      'evaluated_at', CURRENT_TIMESTAMP()::STRING
    )::VARIANT
  {% endset %}

  {% set create_sql %}
    CREATE OR REPLACE TABLE {{ results_fqn }} AS
    SELECT d.*, {{ metadata_sql }} AS run_metadata
    FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
      '{{ parts[0] }}', '{{ parts[1] }}', '{{ parts[2] }}', 'CORTEX AGENT', '{{ run_name }}'
    )) d
  {% endset %}

  {% if execute %}
    {% do run_query(create_sql) %}
    {% do log("Wrote eval results table " ~ results_fqn ~ " (evaluated " ~ evaluated_version ~ ", spec_md5=" ~ spec_hash ~ ")", info=True) %}
  {% endif %}
  {{ return(results_fqn) }}
{% endmacro %}

{% macro cortex_eval__gate(model_name, results_fqn) %}
  {# Aggregate eval_agg_score by metric and compare to declared thresholds.
     Empty summary against any threshold is a failure (mirrors the Python
     check_thresholds guard against silently-malformed runs).
     REQ-030 DN-1: tool metrics (tool_selection/execution_accuracy) aggregate
     over in-scope rows only. Boundary rows (out_of_scope/negative) declare no
     expected invocations, so tool metrics score them degenerately; join to the
     dbt-owned dataset on the input text to read test_type. This mirrors the
     Python run_eval.compute_summary filter so the two paths do not diverge. #}
  {% set eval_meta = cortex_eval__get_eval_meta(model_name) %}
  {% set thresholds = eval_meta.get('thresholds', {}) %}
  {% if not execute %}
    {{ return({}) }}
  {% endif %}

  {% set dataset_fqn = cortex_eval__dataset_fqn(model_name) %}
  {% set summary_rows = run_query(
    "SELECT r.metric_name, AVG(r.eval_agg_score) AS avg_score, COUNT(*) AS n "
    ~ "FROM " ~ results_fqn ~ " r "
    ~ "LEFT JOIN " ~ dataset_fqn ~ " ds ON ds.input_query = r.input "
    ~ "WHERE r.metric_name IS NOT NULL AND r.eval_agg_score IS NOT NULL "
    ~ "AND NOT (r.metric_name IN ('tool_selection_accuracy', 'tool_execution_accuracy') "
    ~ "AND COALESCE(ds.output:custom_criteria:test_type::STRING, 'in_scope') <> 'in_scope') "
    ~ "GROUP BY r.metric_name") %}

  {% set summary = {} %}
  {% for row in summary_rows %}
    {% do summary.update({(row[0] | string | lower): row[1] | float}) %}
  {% endfor %}

  {% if thresholds | length > 0 and summary | length == 0 %}
    {{ exceptions.raise_compiler_error("Eval gate: no metrics present in " ~ results_fqn ~ "; run likely malformed") }}
  {% endif %}

  {% set failures = [] %}
  {% for metric, threshold in thresholds.items() %}
    {% set key = metric | lower %}
    {% if key not in summary %}
      {% do failures.append(metric ~ " MISSING (>= " ~ threshold ~ ")") %}
    {% elif summary[key] < (threshold | float) %}
      {% do failures.append(metric ~ "=" ~ ('%.3f' | format(summary[key])) ~ " < " ~ threshold) %}
    {% else %}
      {% do log("  " ~ metric ~ "=" ~ ('%.3f' | format(summary[key])) ~ " >= " ~ threshold ~ " [PASS]", info=True) %}
    {% endif %}
  {% endfor %}

  {% if failures | length > 0 %}
    {{ exceptions.raise_compiler_error("Eval gate FAILED for " ~ model_name ~ ": " ~ (failures | join('; '))) }}
  {% endif %}
  {% do log("Eval gate PASSED for " ~ model_name, info=True) %}
  {{ return(summary) }}
{% endmacro %}

{% macro cortex_eval__run(model_name, run_name=none, dry_run=true, max_attempts=60, interval=15) %}
  {# End-to-end native eval: render -> start -> poll -> results table -> gate.
     Fully dbt-native; run_eval.py stays the Python parity path for local-dataset
     YAML configs. Sandbox-guarded; dry_run previews without mutating. #}
  {% set eval_meta = cortex_eval__get_eval_meta(model_name) %}
  {% set projection = eval_meta.get('projection', 'native_eval') %}
  {% set invocation_slug = invocation_id | replace('-', '') %}
  {% set eval_run_name = run_name or (eval_meta.get('agent') ~ '_' ~ eval_meta.get('name') ~ '_eval_' ~ invocation_slug[:12]) %}
  {% set config_url = '@' ~ cortex_eval__default_stage_fqn() ~ '/' ~ cortex_eval__config_filename(model_name) %}

  {% if dry_run %}
    {% do cortex_eval__render_config(model_name, eval_run_name, none, false) %}
    {% do log("[DRY RUN] would start/poll/gate eval run_name=" ~ eval_run_name, info=True) %}
    {% do log("[DRY RUN] results table would be " ~ cortex_eval__results_fqn(eval_run_name), info=True) %}
    {{ return(eval_run_name) }}
  {% endif %}

  {% do cortex_agent__assert_deploy_target('cortex_eval__run') %}

  {% do cortex_eval__start(model_name, eval_run_name, none, none, false, true) %}
  {% set status = cortex_eval__poll(eval_run_name, config_url, max_attempts, interval) %}
  {% if status != 'COMPLETED' %}
    {{ exceptions.raise_compiler_error("Eval run " ~ eval_run_name ~ " did not complete: " ~ status) }}
  {% endif %}
  {% set results_fqn = cortex_eval__results(model_name, eval_run_name, projection) %}
  {% do cortex_eval__gate(model_name, results_fqn) %}
  {% do log("Eval run complete: " ~ eval_run_name ~ " -> " ~ results_fqn, info=True) %}
  {{ return(results_fqn) }}
{% endmacro %}
