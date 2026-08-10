{% macro cortex_eval__dataset_content_hash(model_name) %}
  {# Evaluation datasets snapshot table content. Use a deterministic content
     hash in the dataset name so dynamic ground truth (for example CURRENT_DATE
     season logic) gets a fresh dataset when the materialized table changes, but
     unchanged content reuses the existing Snowflake dataset and omits the
     `dataset` block on repeat START calls. #}
  {% if not execute %}
    {{ return(invocation_id | replace('-', '')) }}
  {% endif %}
  {% set dataset_fqn = cortex_eval__dataset_fqn(model_name) %}
  {% set hash_sql %}
    SELECT TO_VARCHAR(ABS(HASH_AGG(HASH(input_query, TO_JSON(output))))) AS dataset_hash
    FROM {{ dataset_fqn }}
  {% endset %}
  {% set results = run_query(hash_sql) %}
  {{ return(results.rows[0][0] | string) }}
{% endmacro %}

{% macro cortex_eval__default_dataset_name(model_name, eval_meta, content_hash=none) %}
  {% set agent_slug = eval_meta.get('agent') | upper %}
  {% set eval_slug = eval_meta.get('name') | upper %}
  {% set dataset_hash = content_hash or cortex_eval__dataset_content_hash(model_name) %}
  {{ return(target.database ~ '.' ~ cortex_eval__schema() ~ '.' ~ agent_slug ~ '_' ~ eval_slug ~ '_DS_' ~ dataset_hash) }}
{% endmacro %}

{% macro cortex_eval__hash_named_dataset_name(base_dataset_name, content_hash) %}
  {# Explicit dataset_name is treated as a stable prefix, not a bypass. Content
     still participates in the object name so dynamic ground truth cannot reuse a
     stale dataset after the materialized eval table changes. #}
  {% if not base_dataset_name %}
    {{ return(none) }}
  {% endif %}
  {% if base_dataset_name.endswith('_DS_' ~ content_hash) %}
    {{ return(base_dataset_name) }}
  {% endif %}
  {{ return(base_dataset_name ~ '_DS_' ~ content_hash) }}
{% endmacro %}

{% macro cortex_eval__dataset_exists(dataset_name) %}
  {% if not execute %}
    {{ return(false) }}
  {% endif %}
  {% set parts = dataset_name.split('.') %}
  {% set object_name = parts[-1] %}
  {% set schema_fqn = parts[0] ~ '.' ~ parts[1] %}
  {% set results = run_query("SHOW DATASETS IN SCHEMA " ~ schema_fqn) %}
  {% set col_names = results.column_names | map('lower') | list %}
  {% set name_idx = col_names.index('name') if 'name' in col_names else 1 %}
  {% for row in results %}
    {% if (row[name_idx] | string | upper) == (object_name | upper) %}
      {{ return(true) }}
    {% endif %}
  {% endfor %}
  {{ return(false) }}
{% endmacro %}

{% macro cortex_eval__native_config(eval_meta, agent_fqn, dataset_fqn, eval_dataset_name, label, include_dataset_block=true) %}
  {% set eval_config = {
    'evaluation': {
      'agent_params': {
        'agent_name': agent_fqn,
        'agent_type': 'CORTEX AGENT'
      },
      'run_params': {
        'label': label,
        'description': eval_meta.get('description', 'Automated evaluation')
      },
      'source_metadata': {
        'type': 'dataset',
        'dataset_name': eval_dataset_name
      }
    },
    'metrics': eval_meta.get('metrics', [])
  } %}
  {% if include_dataset_block %}
    {% do eval_config.update({
      'dataset': {
        'dataset_type': 'CORTEX AGENT',
        'table_name': dataset_fqn,
        'dataset_name': eval_dataset_name,
        'column_mapping': {
          'query_text': 'INPUT_QUERY',
          'ground_truth': 'OUTPUT'
        }
      }
    }) %}
  {% endif %}
  {{ return(eval_config) }}
{% endmacro %}

{% macro cortex_eval__build_config(model_name, run_name=none, dataset_name=none, execute_checks=false, include_dataset=none) %}
  {% do cortex_eval__validate(model_name, execute_checks) %}
  {% set eval_meta = cortex_eval__get_eval_meta(model_name) %}
  {% set exposure = cortex_agent__get_agent(eval_meta.get('agent')) %}
  {% set agent = exposure.meta.get('cortex_agent', {}) %}
  {% set dataset_fqn = cortex_eval__dataset_fqn(model_name) %}
  {% set content_hash = cortex_eval__dataset_content_hash(model_name) %}
  {% set eval_dataset_name = cortex_eval__hash_named_dataset_name(dataset_name, content_hash) or cortex_eval__default_dataset_name(model_name, eval_meta, content_hash) %}
  {% set include_dataset_block = include_dataset %}
  {% if include_dataset_block is none %}
    {% set include_dataset_block = not cortex_eval__dataset_exists(eval_dataset_name) %}
  {% endif %}
  {% set agent_fqn = cortex_agent__target_agent_fqn(agent) %}
  {% set label = run_name or (agent.get('snowflake_name') ~ ' ' ~ eval_meta.get('name') ~ ' evaluation') %}

  {{ return(cortex_eval__native_config(eval_meta, agent_fqn, dataset_fqn, eval_dataset_name, label, include_dataset_block)) }}
{% endmacro %}

{% macro cortex_eval__render_config(model_name, run_name=none, dataset_name=none, execute_checks=false) %}
  {% set eval_config = cortex_eval__build_config(model_name, run_name, dataset_name, execute_checks) %}
  {# JSON is valid YAML and was empirically accepted by EXECUTE_AI_EVALUATION
     on the dbt_focus sandbox (json_probe_* START succeeded on 2026-07-21).
     Use adapter-native serialization rather than hand-built indentation and
     quoting, eliminating an entire class of YAML corruption bugs. #}
  {% set rendered = tojson(eval_config) %}
  {% if '$$' in rendered %}
    {{ exceptions.raise_compiler_error("Rendered eval config contains '$$' delimiter") }}
  {% endif %}
  {% do log(rendered, info=True) %}
  {{ return(rendered) }}
{% endmacro %}

{% macro cortex_eval__default_stage_fqn() %}
  {{ return(target.database ~ '.' ~ cortex_agent__schema() ~ '.EVAL_CONFIG_STAGE') }}
{% endmacro %}

{% macro cortex_eval__execution_plan(agent_name, suite_name) %}
  {% set plan_schema_version = 1 %}
  {% set dataset_token = '__DBT_CORTEX_AGENT_DATASET_NAME__' %}
  {% set node = cortex_eval__get_suite(agent_name, suite_name) %}
  {% set model_name = node.name %}
  {% do cortex_eval__validate(model_name, false) %}
  {% set eval_meta = cortex_eval__get_eval_meta(model_name) %}
  {% set exposure = cortex_agent__get_agent(agent_name) %}
  {% set agent = exposure.meta.get('cortex_agent', {}) %}
  {% set metrics = eval_meta.get('metrics', []) %}
  {% set metric_names = cortex_eval__metric_names(metrics) %}
  {% set thresholds = eval_meta.get('thresholds', {}) %}
  {% set tolerances = eval_meta.get('regression_tolerances', {}) %}
  {% set dataset_fqn = cortex_eval__dataset_fqn(model_name) %}
  {% set agent_fqn = cortex_agent__target_agent_fqn(agent) %}
  {% set stage_fqn = cortex_eval__default_stage_fqn() %}
  {% set config_filename_template = model_name ~ '__RUN_NAME__.json' %}
  {% set ordered_refs = [] %}
  {% for question in eval_meta.get('questions', []) %}
    {% do ordered_refs.append(question.get('ground_truth_ref')) %}
  {% endfor %}
  {% set native_config = cortex_eval__native_config(
    eval_meta, agent_fqn, dataset_fqn, dataset_token, agent_name ~ '/' ~ suite_name, true
  ) %}
  {% set identity = {
    'agent_name': agent_name,
    'suite_name': suite_name,
    'eval_model': model_name,
    'agent_fqn': agent_fqn,
    'dataset_fqn': dataset_fqn,
    'stage_fqn': stage_fqn,
    'target_name': target.name,
    'target_role': target.role,
    'target_database': (target.database | upper),
    'target_schema': (target.schema | upper),
    'target_warehouse': target.warehouse
  } %}
  {% set signature_inputs = {
    'plan_schema_version': plan_schema_version,
    'identity': identity,
    'native_eval_config': native_config,
    'metric_names': metric_names,
    'thresholds': thresholds,
    'regression_tolerances': tolerances,
    'ordered_ground_truth_refs': ordered_refs
  } %}
  {% set signature_material = tojson(signature_inputs) %}
  {% set plan = {
    'schema_version': plan_schema_version,
    'identity': identity,
    'native_eval_config': native_config,
    'dataset_name_token': dataset_token,
    'config_filename_template': config_filename_template,
    'metric_names': metric_names,
    'thresholds': thresholds,
    'regression_tolerances': tolerances,
    'ordered_ground_truth_refs': ordered_refs,
    'signature_material': signature_material,
    'suite_signature': local_md5(signature_material)
  } %}
  {% do log('CORTEX_EVAL_PLAN_JSON=' ~ tojson(plan), info=True) %}
  {{ return(tojson(plan)) }}
{% endmacro %}

{% macro cortex_eval__start(model_name, run_name=none, dataset_name=none, stage_fqn=none, dry_run=true, execute_checks=true) %}
  {% set eval_meta = cortex_eval__get_eval_meta(model_name) %}
  {% set invocation_slug = invocation_id | replace('-', '') %}
  {% set eval_run_name = run_name or (eval_meta.get('agent') ~ '_' ~ eval_meta.get('name') ~ '_eval_' ~ invocation_slug[:12]) %}
  {% set eval_stage = stage_fqn or cortex_eval__default_stage_fqn() %}
  {% set config_yaml = cortex_eval__render_config(model_name, eval_run_name, dataset_name, execute_checks) %}
  {% set filename = cortex_eval__config_filename(model_name) %}
  {% set config_url = '@' ~ eval_stage ~ '/' ~ filename %}

  {% if dry_run %}
    {% set rendered_config = cortex_eval__build_config(model_name, eval_run_name, dataset_name, execute_checks) %}
    {% if rendered_config.get('dataset') %}
      {% do log('[DRY RUN] would create dataset from table ' ~ rendered_config['dataset']['table_name'] ~ ' as ' ~ rendered_config['dataset']['dataset_name'], info=True) %}
    {% else %}
      {% do log('[DRY RUN] would reuse existing dataset ' ~ rendered_config['evaluation']['source_metadata']['dataset_name'], info=True) %}
    {% endif %}
    {% do log('[DRY RUN] would create stage ' ~ eval_stage, info=True) %}
    {% do log('[DRY RUN] would upload eval config to ' ~ config_url, info=True) %}
    {% do log('[DRY RUN] would start EXECUTE_AI_EVALUATION run_name=' ~ eval_run_name, info=True) %}
    {{ return(eval_run_name) }}
  {% endif %}

  {% do cortex_agent__assert_deploy_target('cortex_eval__start') %}

  {% if not execute %}
    {{ return(eval_run_name) }}
  {% endif %}

  {% do run_query('CREATE STAGE IF NOT EXISTS ' ~ eval_stage) %}
  {% do run_query("COPY INTO " ~ config_url ~ " FROM (SELECT $$" ~ config_yaml ~ "$$) FILE_FORMAT = (TYPE = 'CSV' FIELD_DELIMITER = NONE RECORD_DELIMITER = NONE COMPRESSION = NONE) SINGLE = TRUE OVERWRITE = TRUE") %}
  {% do run_query("CALL EXECUTE_AI_EVALUATION('START', OBJECT_CONSTRUCT('run_name', '" ~ eval_run_name ~ "'), '" ~ config_url ~ "')") %}
  {% do log('Started Cortex Agent evaluation run_name=' ~ eval_run_name ~ ' config=' ~ config_url, info=True) %}
  {{ return(eval_run_name) }}
{% endmacro %}
