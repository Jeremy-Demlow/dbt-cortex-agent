# Macro reference

The `cortex_agent` materialization is the deployment API. Package CLI commands
call the lifecycle macros below; consumers should normally use the CLI rather
than invoking mutating macros directly.

## Agent lifecycle

| Macro | Important arguments | Remote/mutation behavior |
|---|---|---|
| `cortex_agent__version_state_for_model` | `agent_name` | Read-only version/default/alias inventory |
| `cortex_agent__route_version` | `agent_name`, `to_version`, `alias`, `set_default=false` | Guarded alias and optional DEFAULT reconciliation |
| `cortex_agent__drop` | `agent_name` | Guarded retirement used only after CLI confirmation |

These macros validate the manifest-owned physical identity and package
target/database policy. Python contains no Agent DDL.

## Evaluations

| Macro/test | Important arguments | Behavior |
|---|---|---|
| `cortex_eval__validate` | `model_name`, `execute_checks=false` | Optional live table checks |
| `cortex_eval__render_dataset_fqn` | `model_name` | Logs resolved table FQN |
| `cortex_eval__render_config` | `model_name`, run/dataset names, checks | May query table/dataset inventory |
| `cortex_eval__execution_plan` | `agent_name`, `suite_name` | Emits one offline schema-versioned JSON plan for Python execution |
| `cortex_eval__start` | names, stage, `dry_run=true`, checks | Apply starts built-in evaluation |
| `cortex_eval__run` | `model_name`, `dry_run=true`, polling controls | On-demand built-in loop and threshold gate |
| `dbt_cortex_agent.cortex_eval_question_coverage` | refs/tools/minimums | Generic data test |
| `dbt_cortex_agent.cortex_eval__current_season_cte` | date relation | Domain-specific ski-season helper |
| `dbt_cortex_agent.cortex_eval__last_complete_season_cte` | date relation | Domain-specific ski-season helper |
| `dbt_cortex_agent.cortex_eval__assemble` | CTE names | Eval-row assembly helper |

Model-SQL helper calls and generic tests must be package-qualified. Lookup,
render-component, hashing, readiness, polling, and result-table helper macros are
internal and may change without compatibility guarantees.
