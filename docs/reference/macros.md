# Macro reference

The `cortex_agent` materialization is the deployment API. Package CLI commands
call the lifecycle macros below; consumers should normally use the CLI rather
than invoking mutating macros directly.

## Agent lifecycle

| Macro | Important arguments | Remote/mutation behavior |
|---|---|---|
| `cortex_agent__version_state_for_model` | `agent_name` | Read-only version/default/alias inventory |
| `cortex_agent__route_version` | `agent_name`, `to_version`, `alias`, `set_default=false`, `expected_agent_fqn=none` | Guarded alias and optional DEFAULT reconciliation |
| `cortex_agent__drop` | `agent_name`, `expected_agent_fqn=none` | Guarded retirement used only after CLI confirmation |

These macros validate the manifest-owned physical identity and package
target/database policy. Python contains no Agent DDL.

The CLI always binds routing and retirement to the planned physical FQN. Direct
macro callers can supply `expected_agent_fqn` to enforce the same check before
mutation. Omitting it preserves the lower-level graph-resolved interface; target,
database, version, and alias guards still apply. Alias and DEFAULT phases each
enforce the supplied expectation, including composite `route_version` calls.

## Evaluations

| Macro/test | Important arguments | Behavior |
|---|---|---|
| `cortex_eval__validate` | `model_name`, `execute_checks=false` | Optional live table checks |
| `cortex_eval__render_dataset_fqn` | `model_name` | Logs resolved table FQN |
| `cortex_eval__render_config` | `model_name`, run/dataset names, `execute_checks=false`, `dry_run=false` | Normal rendering queries content hash/dataset inventory; explicit dry run is query-free, non-executable preview |
| `cortex_eval__execution_plan` | `agent_name`, `suite_name` | Emits one offline schema-versioned JSON plan for Python execution |
| `cortex_eval__start` | names, stage, `dry_run=true`, checks | Query-free preview by default; apply starts built-in evaluation |
| `cortex_eval__run` | `model_name`, `dry_run=true`, polling controls | Query-free preview by default; on-demand built-in loop and threshold gate on apply |
| `dbt_cortex_agent.cortex_eval_question_coverage` | refs/tools/minimums | Generic data test |
| `dbt_cortex_agent.cortex_eval__current_season_cte` | date relation | Domain-specific ski-season helper |
| `dbt_cortex_agent.cortex_eval__last_complete_season_cte` | date relation | Domain-specific ski-season helper |
| `dbt_cortex_agent.cortex_eval__assemble` | CTE names | Eval-row assembly helper |

Model-SQL helper calls and generic tests must be package-qualified. Lookup,
render-component, hashing, readiness, polling, and result-table helper macros are
internal and may change without compatibility guarantees.

The config renderer's trailing `dry_run` argument preserves existing positional
calls. `execute_checks=false` alone does not disable content-hash or inventory
queries. Use `dry_run=true` for no-query rendering, even with dbt `execute=true`.
It suppresses requested live checks but retains local metadata validation.
`cortex_eval__build_config` accepts the same trailing flag after `include_dataset`.

Previews use the `preview_unresolved` dataset-hash sentinel and a `preview` object
with `executable: false` and `dataset_exists: null`. Unless dataset inclusion is
explicitly requested, the create/reuse choice is unknown and the dataset block
is omitted. These configs are not executable START configs or signed execution
plans: resolve real content and inventory through normal rendering before use.
Rendering under dbt `execute=false` has the same unresolved semantics. The
separate `cortex_eval__execution_plan` contract and its signatures are unchanged.
