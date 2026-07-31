# Public macro reference

Public macros default to non-mutating behavior where applicable.

## Agent lifecycle

| Macro | Important arguments | Remote/mutation behavior |
|---|---|---|
| `cortex_agent__validate` | `agent_name`, `projection='canonical'` | Structural; optional staged LIST |
| `cortex_agent__render_spec` | `agent_name`, `projection='canonical'` | Non-mutating |
| `cortex_agent__deploy` | `agent_name`, `projection='canonical'`, `dry_run=true`, `alias` | Apply is sandbox-guarded |
| `cortex_agent__build` | `projection='native_eval'`, `dry_run=true`, `alias` | Iterates enabled exposures |
| `cortex_agent__grant_usage` | `agent_name`, `projection`, `dry_run=true` | Apply grants Agent usage |
| `cortex_agent__set_alias` | `agent_name`, `alias`, `to_version` or `from_alias`, `projection`, `dry_run=true` | Apply moves alias |
| `cortex_agent__promote_alias` | `agent_name`, `from_alias`, `to_alias`, `projection`, `dry_run=true` | Alias wrapper |
| `cortex_agent__rollback_alias` | `agent_name`, `alias`, `to_version`, `projection`, `dry_run=true` | Alias wrapper |

Provide exactly one of `to_version` and `from_alias` to `set_alias`.

## Evaluations

| Macro/test | Important arguments | Behavior |
|---|---|---|
| `cortex_eval__validate` | `model_name`, `execute_checks=false` | Optional live table checks |
| `cortex_eval__render_dataset_fqn` | `model_name` | Logs resolved table FQN |
| `cortex_eval__render_config` | `model_name`, run/dataset names, checks | May query table/dataset inventory |
| `cortex_eval__start` | names, stage, `dry_run=true`, checks | Apply starts native evaluation |
| `cortex_eval__run` | `model_name`, `dry_run=true`, polling controls | On-demand native loop and threshold gate |
| `dbt_cortex_agent.cortex_eval_question_coverage` | refs/tools/minimums | Generic data test |
| `dbt_cortex_agent.cortex_eval__current_season_cte` | date relation | Domain-specific ski-season helper |
| `dbt_cortex_agent.cortex_eval__last_complete_season_cte` | date relation | Domain-specific ski-season helper |
| `dbt_cortex_agent.cortex_eval__assemble` | CTE names | Eval-row assembly helper |

Model-SQL helper calls and generic tests must be package-qualified. Lookup,
render-component, hashing, readiness, polling, and result-table helper macros are
internal and may change without compatibility guarantees.
