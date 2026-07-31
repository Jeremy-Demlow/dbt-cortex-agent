# Variables

Override package vars in the consuming project's `dbt_project.yml` or `--vars`.

| Variable | Default | Purpose |
|---|---|---|
| `cortex_agent_deploy_target` | `dbt_focus` | Only target allowed to mutate |
| `cortex_agent_schema` | `AGENTS` | Agent and eval-config-stage schema |
| `cortex_eval_schema` | `EVAL` | Eval dataset/results schema |
| `cortex_agent_skill_stage` | `SKILL_STAGE` | Consumer skill-path convention |
| `cortex_agent_default_model` | `claude-sonnet-4-5` | Default orchestration model |
| `code_execution_enabled` | `false` | Global code-execution render gate |
| `force_agent_recreate` | `false` | Bypass hash no-change skip |
| `mcp_deploy_enabled` | `false` | Execute MCP attachment DDL |
| `cortex_agent_validate_staged_skills` | site-dependent | False for preview validation; true for mutating canonical deploy unless explicitly overridden |
| `cortex_agent_env_suffixes` | `{dev: _DEV, dbt_focus: _DBT_FOCUS}` | Fallback target name suffixes |
| `cortex_agent_eval_suffix` | `_EVAL` | Native-eval Agent name suffix |

`cortex_agent_skill_stage` is read by consumer property YAML rather than by a
package macro. Keep it aligned with the actual stage used by the upload tooling.
