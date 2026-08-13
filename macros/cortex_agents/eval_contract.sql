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

{% macro cortex_eval__get_suite(agent_name, suite_name) %}
  {% set matches = [] %}
  {% set nodes = graph.nodes.values() if graph.nodes is defined else graph.get('nodes', {}).values() %}
  {% for node in nodes %}
    {% set resource_type = node.resource_type if node.resource_type is defined else node.get('resource_type') %}
    {% if node is mapping %}
      {% set eval_meta = node.get('config', {}).get('meta', {}).get('cortex_eval', {}) or node.get('meta', {}).get('cortex_eval', {}) %}
    {% else %}
      {% set eval_meta = node.config.meta.get('cortex_eval', {}) if node.config.meta is mapping else {} %}
    {% endif %}
    {% if resource_type == 'model' and eval_meta and eval_meta.get('enabled', true) != false and eval_meta.get('agent') == agent_name and eval_meta.get('name') == suite_name %}
      {% do matches.append(node) %}
    {% endif %}
  {% endfor %}

  {% if matches | length != 1 %}
    {{ exceptions.raise_compiler_error("Expected exactly one enabled cortex_eval for Agent '" ~ agent_name ~ "' and suite '" ~ suite_name ~ "', found " ~ (matches | length)) }}
  {% endif %}
  {{ return(matches[0]) }}
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

{% macro cortex_eval__native_supported_tool_names(agent_name) %}
  {% set resource = cortex_agent__get_agent(agent_name) %}
  {% set agent = cortex_agent__agent_meta(resource) %}
  {% if cortex_agent__is_model(resource) %}
    {{ return(agent.get('evaluation', {}).get('native_tools', [])) }}
  {% endif %}
  {% set supported = [] %}
  {% for tool in agent.get('tools', []) %}
    {% if tool.get('type') in ['cortex_analyst_text_to_sql', 'cortex_search', 'generic'] %}
      {% do supported.append(tool.get('name')) %}
    {% endif %}
  {% endfor %}
  {% if agent.get('capabilities', {}).get('web_search', {}).get('enabled') %}
    {% do supported.append('web_search') %}
  {% endif %}
  {{ return(supported) }}
{% endmacro %}

{% macro cortex_eval__unsupported_native_tool_claims(agent_name) %}
  {% set resource = cortex_agent__get_agent(agent_name) %}
  {% set agent = cortex_agent__agent_meta(resource) %}
  {% if cortex_agent__is_model(resource) %}
    {{ return(agent.get('evaluation', {}).get('unsupported_tools', {})) }}
  {% endif %}
  {% set capabilities = agent.get('capabilities', {}) %}
  {% set unsupported = {} %}
  {% for skill in capabilities.get('skills', []) %}
    {% do unsupported.update({skill.get('name'): 'skill'}) %}
  {% endfor %}
  {% for connector in capabilities.get('mcp_connectors', []) %}
    {% if connector.get('enabled') %}
      {% do unsupported.update({connector.get('name'): 'MCP connector'}) %}
    {% endif %}
  {% endfor %}
  {% if capabilities.get('code_execution', {}).get('enabled') %}
    {% do unsupported.update({'code_execution': 'code execution'}) %}
  {% endif %}
  {% if capabilities.get('data_to_chart', {}).get('enabled') %}
    {% do unsupported.update({'data_to_chart': 'data-to-chart capability'}) %}
  {% endif %}
  {{ return(unsupported) }}
{% endmacro %}

{% macro cortex_eval__capability_evidence(agent_name, invoked_tools=[], evaluation_completed=false) %}
  {% set resource = cortex_agent__get_agent(agent_name) %}
  {% set agent = cortex_agent__agent_meta(resource) %}
  {% if cortex_agent__is_model(resource) %}
    {% set evidence = [] %}
    {% for tool_name in agent.get('evaluation', {}).get('native_tools', []) %}
      {% do evidence.append({
        'capability': 'tool',
        'name': tool_name,
        'classification': 'invoked' if tool_name in invoked_tools else ('completed_with_attachment' if evaluation_completed else 'attached')
      }) %}
    {% endfor %}
    {% for capability_name, capability_type in agent.get('evaluation', {}).get('unsupported_tools', {}).items() %}
      {% do evidence.append({
        'capability': capability_type,
        'name': capability_name,
        'classification': 'invoked' if capability_name in invoked_tools else 'indeterminate'
      }) %}
    {% endfor %}
    {{ return(evidence) }}
  {% endif %}
  {% set capabilities = agent.get('capabilities', {}) %}
  {% set spec = cortex_agent__build_spec(agent_name) %}
  {% set evidence = [] %}
  {% set rendered_names = [] %}
  {% for tool in spec.get('tools', []) %}
    {% set name = tool.get('tool_spec', {}).get('name') %}
    {% do rendered_names.append(name) %}
    {% do evidence.append({
      'capability': 'tool',
      'name': name,
      'classification': 'invoked' if name in invoked_tools else ('completed_with_attachment' if evaluation_completed else 'attached')
    }) %}
  {% endfor %}
  {% for skill in spec.get('skills', []) %}
    {% set name = skill.get('name') %}
    {% set classification = 'invoked' if name in invoked_tools else ('completed_with_attachment' if evaluation_completed else 'attached') %}
    {% do evidence.append({'capability': 'skill', 'name': name, 'classification': classification}) %}
  {% endfor %}
  {% if spec.get('skills', []) | length == 0 %}
    {% do evidence.append({'capability': 'skills', 'name': 'skills', 'classification': 'absent'}) %}
  {% endif %}
  {% set code_classification = 'invoked' if 'code_execution' in invoked_tools else (('completed_with_attachment' if evaluation_completed else 'attached') if 'code_execution' in rendered_names else 'absent') %}
  {% do evidence.append({'capability': 'code_execution', 'name': 'code_execution', 'classification': code_classification}) %}
  {% set enabled_mcp = [] %}
  {% for connector in capabilities.get('mcp_connectors', []) %}
    {% if connector.get('enabled') %}
      {% do enabled_mcp.append(connector) %}
    {% endif %}
  {% endfor %}
  {% if enabled_mcp | length == 0 %}
    {% do evidence.append({'capability': 'mcp', 'name': 'mcp', 'classification': 'absent'}) %}
  {% else %}
    {% for connector in enabled_mcp %}
      {% set name = connector.get('name') %}
      {% do evidence.append({'capability': 'mcp', 'name': name, 'classification': 'invoked' if name in invoked_tools else 'indeterminate'}) %}
    {% endfor %}
  {% endif %}
  {{ return(evidence) }}
{% endmacro %}

{% macro cortex_eval__render_capability_evidence(agent_name, invoked_tools=[], evaluation_completed=false) %}
  {% set evidence = cortex_eval__capability_evidence(agent_name, invoked_tools, evaluation_completed) %}
  {% do log('CORTEX_AGENT_CAPABILITY_EVIDENCE=' ~ tojson(evidence), info=True) %}
  {{ return(evidence) }}
{% endmacro %}

{% macro cortex_eval__validate(model_name, execute_checks=false) %}
  {% set node = cortex_eval__get_eval(model_name) %}
  {% set eval_meta = cortex_eval__get_eval_meta(model_name) %}
  {% set required = ['name', 'agent', 'metrics', 'questions'] %}

  {% if eval_meta.get('projection') is not none %}
    {{ exceptions.raise_compiler_error("Eval model '" ~ model_name ~ "' must not define config.meta.cortex_eval.projection; evaluations use the exposure's normal Agent FQN") }}
  {% endif %}

  {% for field in required %}
    {% if eval_meta.get(field) is none %}
      {{ exceptions.raise_compiler_error("Eval model '" ~ model_name ~ "' missing config.meta.cortex_eval." ~ field) }}
    {% endif %}
  {% endfor %}

  {% set resource = cortex_agent__get_agent(eval_meta.get('agent')) %}
  {% set agent = cortex_agent__agent_meta(resource) %}
  {% set metrics = eval_meta.get('metrics', []) %}
  {% set questions = eval_meta.get('questions', []) %}
  {% set metric_names = cortex_eval__metric_names(metrics) %}
  {% set question_ids = [] %}
  {% set ground_truth_refs = [] %}

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
    {% if question.get('id') in question_ids %}
      {{ exceptions.raise_compiler_error("Eval model '" ~ model_name ~ "' has duplicate question id '" ~ question.get('id') ~ "'") }}
    {% endif %}
    {% if question.get('ground_truth_ref') in ground_truth_refs %}
      {{ exceptions.raise_compiler_error("Eval model '" ~ model_name ~ "' has duplicate ground_truth_ref '" ~ question.get('ground_truth_ref') ~ "'") }}
    {% endif %}
    {% do question_ids.append(question.get('id')) %}
    {% do ground_truth_refs.append(question.get('ground_truth_ref')) %}
  {% endfor %}

  {% set native_supported_tool_names = cortex_eval__native_supported_tool_names(eval_meta.get('agent')) %}
  {% set unsupported_native_tool_claims = cortex_eval__unsupported_native_tool_claims(eval_meta.get('agent')) %}
  {% for question in questions %}
    {% set expected_tools = question.get('expected_tools', []) %}
    {% if expected_tools is string or expected_tools is not sequence %}
      {{ exceptions.raise_compiler_error("Eval question '" ~ question.get('id') ~ "' expected_tools must be a list of tool names") }}
    {% endif %}
    {% for expected_tool in expected_tools %}
      {% if expected_tool is not string or not expected_tool | trim %}
        {{ exceptions.raise_compiler_error("Eval question '" ~ question.get('id') ~ "' expected_tools entries must be non-empty strings") }}
      {% endif %}
      {% if expected_tool in native_supported_tool_names %}
      {% elif unsupported_native_tool_claims.get(expected_tool) %}
        {{ exceptions.raise_compiler_error("Eval question '" ~ question.get('id') ~ "' cannot claim native coverage for " ~ unsupported_native_tool_claims.get(expected_tool) ~ " '" ~ expected_tool ~ "'; use smoke, integration, or other capability-specific proof") }}
      {% else %}
        {{ exceptions.raise_compiler_error("Eval question '" ~ question.get('id') ~ "' expects undeclared or unsupported native tool '" ~ expected_tool ~ "'; declared native-supported tools are: " ~ (native_supported_tool_names | join(', '))) }}
      {% endif %}
    {% endfor %}
  {% endfor %}

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

  {% do log("Validated cortex eval model: " ~ model_name ~ " (single deployed Agent)", info=True) %}
  {{ return(True) }}
{% endmacro %}
