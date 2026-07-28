{% macro cortex_eval__get_eval(model_name) %}
  {% set matches = [] %}
  {% set nodes = graph.nodes.values() if graph.nodes is defined else graph.get('nodes', {}).values() %}
  {% for node in nodes %}
    {% set resource_type = node.resource_type if node.resource_type is defined else node.get('resource_type') %}
    {% set name = node.name if node.name is defined else node.get('name') %}
    {% if resource_type == 'model' and name == model_name %}
      {% if node is mapping %}
        {% set eval_meta = node.get('config', {}).get('meta', {}).get('cortex_eval', {}) or node.get('meta', {}).get('cortex_eval', {}) %}
      {% else %}
        {% set eval_meta = node.config.meta.get('cortex_eval', {}) if node.config.meta is mapping else {} %}
      {% endif %}
      {% if eval_meta %}
        {% do matches.append(node) %}
      {% endif %}
    {% endif %}
  {% endfor %}

  {% if matches | length == 0 %}
    {{ exceptions.raise_compiler_error("No model with config.meta.cortex_eval found for '" ~ model_name ~ "'") }}
  {% endif %}
  {% if matches | length > 1 %}
    {{ exceptions.raise_compiler_error("Multiple models with config.meta.cortex_eval found for '" ~ model_name ~ "'") }}
  {% endif %}

  {{ return(matches[0]) }}
{% endmacro %}

{% macro cortex_eval__get_eval_meta(model_name) %}
  {% set node = cortex_eval__get_eval(model_name) %}
  {{ return(node.config.meta.get('cortex_eval', {})) }}
{% endmacro %}

{% macro cortex_eval__dataset_fqn(model_name) %}
  {% set node = cortex_eval__get_eval(model_name) %}
  {% set materialized = node.config.get('materialized') %}

  {% if materialized != 'table' %}
    {{ exceptions.raise_compiler_error("Eval model '" ~ model_name ~ "' must be materialized as table, got '" ~ materialized ~ "'") }}
  {% endif %}

  {% set database_name = (node.database or target.database) | upper %}
  {% set schema_name = node.schema | upper %}
  {% set identifier = (node.alias or node.name) | upper %}
  {{ return(database_name ~ '.' ~ schema_name ~ '.' ~ identifier) }}
{% endmacro %}

{% macro cortex_eval__render_dataset_fqn(model_name) %}
  {% set dataset_fqn = cortex_eval__dataset_fqn(model_name) %}
  {% do log("CORTEX_EVAL_DATASET_FQN=" ~ dataset_fqn, info=True) %}
  {{ return(dataset_fqn) }}
{% endmacro %}

{% macro cortex_eval__metric_names(metrics) %}
  {% set names = [] %}
  {% for metric in metrics %}
    {% if metric is string %}
      {% do names.append(metric) %}
    {% elif metric is mapping and metric.get('name') %}
      {% do names.append(metric.get('name')) %}
    {% endif %}
  {% endfor %}
  {{ return(names) }}
{% endmacro %}

{% macro cortex_eval__validate(model_name, execute_checks=false) %}
  {% set node = cortex_eval__get_eval(model_name) %}
  {% set eval_meta = cortex_eval__get_eval_meta(model_name) %}
  {% set required = ['name', 'agent', 'projection', 'metrics', 'questions'] %}

  {% for field in required %}
    {% if eval_meta.get(field) is none %}
      {{ exceptions.raise_compiler_error("Eval model '" ~ model_name ~ "' missing config.meta.cortex_eval." ~ field) }}
    {% endif %}
  {% endfor %}

  {% set agent_exposure = cortex_agent__get_agent(eval_meta.get('agent')) %}
  {% set agent = agent_exposure.meta.get('cortex_agent', {}) %}
  {% set projection = eval_meta.get('projection', 'native_eval') %}
  {% set metrics = eval_meta.get('metrics', []) %}
  {% set questions = eval_meta.get('questions', []) %}
  {% set metric_names = cortex_eval__metric_names(metrics) %}

  {% if metrics | length == 0 %}
    {{ exceptions.raise_compiler_error("Eval model '" ~ model_name ~ "' must define at least one metric") }}
  {% endif %}
  {% if questions | length == 0 %}
    {{ exceptions.raise_compiler_error("Eval model '" ~ model_name ~ "' must define at least one question") }}
  {% endif %}

  {% for metric in metrics %}
    {% if metric is string %}
    {% elif metric is mapping %}
      {% if not metric.get('name') %}
        {{ exceptions.raise_compiler_error("Eval model '" ~ model_name ~ "' has a custom metric missing name") }}
      {% endif %}
      {% if not metric.get('prompt') %}
        {{ exceptions.raise_compiler_error("Custom metric '" ~ metric.get('name') ~ "' missing prompt") }}
      {% endif %}
    {% else %}
      {{ exceptions.raise_compiler_error("Eval model '" ~ model_name ~ "' has an unsupported metric entry") }}
    {% endif %}
  {% endfor %}

  {% for question in questions %}
    {% if not question.get('id') %}
      {{ exceptions.raise_compiler_error("Eval model '" ~ model_name ~ "' has a question missing id") }}
    {% endif %}
    {% if not question.get('ground_truth_ref') %}
      {{ exceptions.raise_compiler_error("Eval question '" ~ question.get('id') ~ "' must define ground_truth_ref") }}
    {% endif %}
  {% endfor %}

  {% set spec = cortex_agent__build_spec(eval_meta.get('agent'), projection) %}
  {% set rendered_tool_names = [] %}
  {% for tool in spec.get('tools', []) %}
    {% do rendered_tool_names.append(tool.get('tool_spec', {}).get('name')) %}
  {% endfor %}
  {% for question in questions %}
    {% for expected_tool in question.get('expected_tools', []) %}
      {% if expected_tool not in rendered_tool_names %}
        {% set render_label = 'native-eval projection' if projection == 'native_eval' else 'canonical render' %}
        {{ exceptions.raise_compiler_error("Eval question '" ~ question.get('id') ~ "' expects tool '" ~ expected_tool ~ "', but the " ~ render_label ~ " renders only: " ~ (rendered_tool_names | join(', '))) }}
      {% endif %}
    {% endfor %}
  {% endfor %}

  {% set enabled_mcp = [] %}
  {% for connector in agent.get('capabilities', {}).get('mcp_connectors', []) %}
    {% if connector.get('enabled') %}
      {% do enabled_mcp.append(connector.get('name', '<unnamed>')) %}
    {% endif %}
  {% endfor %}
  {% if projection == 'canonical' and enabled_mcp | length > 0 %}
    {{ exceptions.raise_compiler_error("Built-in Cortex Agent Evaluations do not support MCP connectors in the canonical render: " ~ (enabled_mcp | join(', ')) ~ ". Use the native-eval projection.") }}
  {% endif %}

  {% do cortex_eval__dataset_fqn(model_name) %}

  {% set run_live_checks = execute_checks in [true, 'true', 'True'] %}
  {% if run_live_checks and execute %}
    {% set dataset_fqn = cortex_eval__dataset_fqn(model_name) %}
    {% set describe_result = run_query("DESCRIBE TABLE " ~ dataset_fqn) %}
    {% set columns = [] %}
    {% for row in describe_result %}
      {% do columns.append(row[0] | upper) %}
    {% endfor %}
    {% if 'INPUT_QUERY' not in columns or 'OUTPUT' not in columns %}
      {{ exceptions.raise_compiler_error("Eval dataset '" ~ dataset_fqn ~ "' must contain INPUT_QUERY and OUTPUT columns") }}
    {% endif %}

    {% set count_result = run_query("SELECT COUNT(*) FROM " ~ dataset_fqn) %}
    {% set row_count = count_result.rows[0][0] %}
    {% if row_count == 0 %}
      {{ exceptions.raise_compiler_error("Eval dataset '" ~ dataset_fqn ~ "' is empty") }}
    {% endif %}

    {% if 'answer_correctness' in metric_names or 'logical_consistency' in metric_names %}
      {% set missing_gt = run_query("SELECT COUNT(*) FROM " ~ dataset_fqn ~ " WHERE output:ground_truth_output IS NULL OR TRIM(output:ground_truth_output::STRING) = ''") %}
      {% if missing_gt.rows[0][0] > 0 %}
        {{ exceptions.raise_compiler_error("Eval dataset '" ~ dataset_fqn ~ "' has " ~ missing_gt.rows[0][0] ~ " row(s) missing ground_truth_output") }}
      {% endif %}
    {% endif %}

    {% if 'tool_selection_accuracy' in metric_names or 'tool_execution_accuracy' in metric_names %}
      {# Taxonomy-aware: out_of_scope / negative rows expect NO tool call, so they
         legitimately carry empty ground_truth_invocations. Only in-scope rows (the
         default when test_type is absent) must declare invocations. #}
      {% set missing_invocations = run_query("SELECT COUNT(*) FROM " ~ dataset_fqn ~ " WHERE (output:ground_truth_invocations IS NULL OR ARRAY_SIZE(output:ground_truth_invocations) = 0) AND COALESCE(output:custom_criteria:test_type::STRING, 'in_scope') = 'in_scope'") %}
      {% if missing_invocations.rows[0][0] > 0 %}
        {{ exceptions.raise_compiler_error("Eval dataset '" ~ dataset_fqn ~ "' has " ~ missing_invocations.rows[0][0] ~ " in-scope row(s) missing ground_truth_invocations") }}
      {% endif %}
    {% endif %}

    {% for question in questions %}
      {% set ref = question.get('ground_truth_ref') | replace("'", "''") %}
      {% set ref_count = run_query("SELECT COUNT(*) FROM " ~ dataset_fqn ~ " WHERE output:custom_criteria:ground_truth_ref::STRING = '" ~ ref ~ "'") %}
      {% if ref_count.rows[0][0] != 1 %}
        {{ exceptions.raise_compiler_error("Eval question '" ~ question.get('id') ~ "' ground_truth_ref must map to exactly one row, got " ~ ref_count.rows[0][0]) }}
      {% endif %}
    {% endfor %}
  {% endif %}

  {% set render_label = 'native-eval projection' if projection == 'native_eval' else 'canonical render' %}
  {% do log("Validated cortex eval model: " ~ model_name ~ " (" ~ render_label ~ ")", info=True) %}
  {{ return(True) }}
{% endmacro %}
