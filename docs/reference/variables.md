# dbt variables

Override package vars in the consumer project's `dbt_project.yml` or with dbt
`--vars`. These values belong to the dbt contract; similarly named CLI options
do not replace them.

| Variable | Internal default | Contract |
|---|---|---|
| `cortex_agent_deploy_target` | `dbt_focus` | Target selected for mutation; adopters must set explicitly. |
| `cortex_agent_allowed_targets` | deploy-target singleton | Targets permitted to mutate; set explicitly for reviewability. |
| `cortex_agent_allowed_databases` | `[]` | Databases permitted to mutate; empty fails closed. |
| `cortex_agent_schema` | `AGENTS` | Agent objects and `EVAL_CONFIG_STAGE`. |
| `cortex_eval_schema` | `EVAL` | Materialized eval tables and result tables. |
| `cortex_agent_skill_stage` | `SKILL_STAGE` | Consumer property-YAML convention for skill paths. |
| `cortex_agent_default_model` | `claude-sonnet-4-5` | Orchestration model when exposure metadata omits one. |
| `code_execution_enabled` | `false` | Global code-execution render gate. |
| `force_agent_recreate` | `false` | Bypass no-change skip; review version impact before use. |
| `mcp_deploy_enabled` | `false` | Permit separate MCP attachment DDL. |
| `cortex_agent_validate_staged_skills` | context-dependent | Preview validation defaults false; mutating Agent deploy defaults true. |
| `cortex_agent_env_suffixes` | `{dev: _DEV, dbt_focus: _DBT_FOCUS}` | Physical-name fallback by target. |

`cortex_agent_skill_stage` is read by consumer property YAML, not by a package
macro. Keep it aligned with the real stage in `capabilities.skills[].source.path`.

Mutating CLI commands add independent `--allow-target` and `--allow-database`
gates. Both layers must permit the operation; neither layer grants privileges.