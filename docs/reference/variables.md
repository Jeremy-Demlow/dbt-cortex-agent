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
| `code_execution_enabled` | `false` | Global code-execution render gate. |
| `force_agent_recreate` | `false` | Bypass no-change skip; review version impact before use. |
| `cortex_agent_expected_fqns` | omitted | Internal CLI deploy approval map: manifest `unique_id` to exact physical FQN. Checked before Agent pre-hooks/DDL; unexpected IDs, empty or invalid supplied maps fail closed. Direct builds without it own their approval sequencing. |
| `mcp_deploy_enabled` | `false` | Permit separate MCP attachment DDL. |
| `cortex_agent_validate_staged_skills` | context-dependent | Preview validation defaults false; mutating Agent deploy defaults true. |
| `cortex_agent_env_suffixes` | `{dev: _DEV, dbt_focus: _DBT_FOCUS}` | Physical-name fallback by target. |

`cortex_agent_skill_stage` is read by consumer property YAML, not by a package
macro. Keep it aligned with native `skills[].source.path` and the local upload
contract in `config.meta.cortex_agent.skills[].source.path`.

Mutating CLI commands add independent `--allow-target` and `--allow-database`
gates. Both layers must permit the operation; neither layer grants privileges.

`force_agent_recreate` does not bypass the unfinished-initial-CREATE recovery
guard. See [lifecycle recovery](../guides/lifecycle.md).