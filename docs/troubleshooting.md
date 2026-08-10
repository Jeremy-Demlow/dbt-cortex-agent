# Troubleshooting

Start with doctor; do not bypass a failed diagnostic with `--no-parse`:

```bash
dbt-cortex-agent doctor --project-dir . --target sandbox --json
```

Exit `0` means diagnostics passed, `1` means a diagnostic/gate failed, and `2`
means a controlled configuration/runtime error. Fix the first failure, rerun
doctor, then use the domain command with `--json` for structured evidence.

Use this sequence rather than skipping directly to deploy or evaluation:

1. Run `dbt --version` and `snow --version`; install or select missing executables.
2. Run `dbt deps`, then `dbt parse --no-partial-parse` in the consumer project.
3. Run `doctor` with the intended `--project-dir` and `--target`; fix every `FAIL`.
4. Run `manifest validate --agent <logical-name> --json` and confirm the Agent
   and eval suite are discovered from the fresh manifest.
5. Run `skill plan --agent <logical-name> --json` when the Agent
   declares skills; fix missing local paths before deployment.
6. Run `agent render`, then `agent deploy` without `--apply`; inspect
   `logs/dbt.log` for the rendered spec, physical name, hashes, and dry-run DDL.
7. For an approved Agent apply, supply an explicit connection, matching
   database, and both CLI allowlists. The CLI uploads declared skills first.
8. For evaluation, separately materialize/test the optional eval model after the
   normal Agent is deployed; then preview `eval run` and consider its paid
   `--apply` path. Do not deploy a second Agent.
9. Retain the candidate at
   `<artifact-dir>/candidates/<agent>/<suite>/<run_name>.json`, gate it, compare
   it with `<artifact-dir>/baselines/<agent>/<suite>.json`, and move a baseline
   only through a separately reviewed `accept-baseline --apply`.

| Symptom | Resolution |
|---|---|
| dbt/project/executable failure | Verify `--project-dir`, `--dbt-executable`, dependency install, and profile target; rerun doctor. |
| Snow CLI executable failure | Install Snow CLI or set `--snow-executable`/`SNOW_EXECUTABLE`; rerun doctor. |
| Immutable SHA package version fails | Run `dbt deps` and verify `dbt_packages/dbt_cortex_agent/dbt_project.yml` reports the CLI version. A source-root `dbt_project.yml`, branch revision, missing install, or mismatched installed version is not accepted. |
| `init` completed but no Agent exists | Expected: init only appends dependency and selected project vars; author the exposure, semantic view, and eval model separately. |
| No enabled exposure | Set `config.meta.cortex_agent.enabled: true`; use the logical exposure name. |
| Semantic model does not resolve | Make the model name unique and materialize it as `semantic_view`. |
| Package macro undefined in model SQL | Call package helpers as `dbt_cortex_agent.<macro>`. |
| Macro call in property YAML fails | Property YAML supports `target`, `var`, and `env_var`, not custom macros. |
| Mutation target rejected | Align CLI `--target`/`--allow-target` with `cortex_agent_deploy_target` and `cortex_agent_allowed_targets`. |
| Database allowlist rejected | Pass `--database` matching dbt's target and include it in CLI/dbt allowed databases. |
| Apply says connection is not explicit | Pass `--connection`; `SNOWFLAKE_CONNECTION_NAME` alone does not authorize apply. |
| Missing staged `SKILL.md` | Run `skill plan`, upload the declared directory to the exact stage path, then deploy. |
| Wrong skill directory | Mirror the declared stage suffix under the private/shared layout; do not add name-keyed remapping. |
| Expected eval tool rejected | Use a declared Analyst, Cortex Search, `web_search`, or generic custom tool name. Skills, MCP, code execution, and other capability tools require separate proof. |
| Eval plan works but apply fails | Confirm the normally deployed Agent, materialized eval table, evaluation stage access, explicit connection, matching database, warehouse, and runtime extra. |
| Eval dataset rejected | Require unique `ground_truth_ref`, unique `INPUT_QUERY`, and one valid `OUTPUT` VARIANT per row. |
| Tool metric fails on boundary rows | Set `custom_criteria.test_type`; require invocations only for relevant in-scope rows. |
| Candidate is indeterminate | Check pre/post DEFAULT provenance; do not rerun until green or relax tolerances. |
| Baseline comparison rejected | Keep suite signature/policy compatible and use the accepted baseline's tolerances. |
| Unexpected target suffix | Review `naming.<target>` and `cortex_agent_env_suffixes`; evaluation does not add an Agent suffix. |
| Controlled error lacks JSON on stdout | Errors are emitted to stderr; process exit is `2`. |
| `agent render --json` has no specification | Expected: CLI JSON is an orchestration summary and successful dbt stdout is captured; inspect `logs/dbt.log` or call `cortex_agent__render_spec` directly. |

See the [CLI reference](reference/cli.md) and [configuration model](guides/configuration-model.md).