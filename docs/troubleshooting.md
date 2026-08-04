# Troubleshooting

Start with doctor; do not bypass a failed diagnostic with `--no-parse`:

```bash
dbt-cortex-agent doctor --project-dir . --target sandbox --json
```

Exit `0` means diagnostics passed, `1` means a diagnostic/gate failed, and `2`
means a controlled configuration/runtime error. Fix the first failure, rerun
doctor, then use the domain command with `--json` for structured evidence.

| Symptom | Resolution |
|---|---|
| dbt/project/executable failure | Verify `--project-dir`, `--dbt-executable`, dependency install, and profile target; rerun doctor. |
| No enabled exposure | Set `config.meta.cortex_agent.enabled: true`; use the logical exposure name. |
| Semantic model does not resolve | Make the model name unique and materialize it as `semantic_view`. |
| Package macro undefined in model SQL | Call package helpers as `dbt_cortex_agent.<macro>`. |
| Macro call in property YAML fails | Property YAML supports `target`, `var`, and `env_var`, not custom macros. |
| Mutation target rejected | Align CLI `--target`/`--allow-target` with `cortex_agent_deploy_target` and `cortex_agent_allowed_targets`. |
| Database allowlist rejected | Pass `--database` matching dbt's target and include it in CLI/dbt allowed databases. |
| Apply says connection is not explicit | Pass `--connection`; `SNOWFLAKE_CONNECTION_NAME` alone does not authorize apply. |
| Missing staged `SKILL.md` | Run `skill plan`, upload the declared directory to the exact stage path, then deploy. |
| Wrong skill directory | Mirror the declared stage suffix under the private/shared layout; do not add name-keyed remapping. |
| Expected eval tool missing | Check `projection` and `evaluation_supported`; native eval excludes skills and MCP. |
| Eval plan works but apply fails | Confirm the deployed native-eval Agent, materialized eval table, evaluation stage access, explicit connection, matching database, warehouse, and runtime extra. |
| Eval dataset rejected | Require unique `ground_truth_ref`, unique `INPUT_QUERY`, and one valid `OUTPUT` VARIANT per row. |
| Tool metric fails on boundary rows | Set `custom_criteria.test_type`; require invocations only for relevant in-scope rows. |
| Candidate is indeterminate | Check pre/post DEFAULT provenance; do not rerun until green or relax tolerances. |
| Baseline comparison rejected | Keep suite signature/policy compatible and use the accepted baseline's tolerances. |
| Unexpected `_EVAL`/target suffix | Review `naming.<target>`, `cortex_agent_env_suffixes`, and `cortex_agent_eval_suffix`. |
| Controlled error lacks JSON on stdout | Errors are emitted to stderr; process exit is `2`. |

See the [CLI reference](reference/cli.md) and [configuration model](guides/configuration-model.md).