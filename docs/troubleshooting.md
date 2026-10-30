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
6. Run `dbt compile --select <agent_model>` and inspect the rendered full spec.
7. For an approved Agent apply, upload declared skills and run dependency-aware
   `dbt build --select +<agent_model>` with matching dbt target/database allowlists.
8. For evaluation, separately materialize/test the optional eval model after the
   normal Agent is deployed; then preview `eval run` and consider its paid
   `--apply` path. Do not deploy a second Agent.
9. Retain the candidate at
   `<artifact-dir>/candidates/<target>/<database>/<schema>/<object>/<suite>/<run_name>.json`, gate it, compare
   it with `<artifact-dir>/baselines/<target>/<database>/<schema>/<object>/<suite>.json`, and move a baseline
   only through a separately reviewed `accept-baseline --apply`.

| Symptom | Resolution |
|---|---|
| dbt/project/executable failure | Verify `--project-dir`, `--dbt-executable`, dependency install, and profile target; rerun doctor. |
| Snow CLI executable failure | Install Snow CLI or set `--snow-executable`/`SNOW_EXECUTABLE`; rerun doctor. |
| Immutable SHA package version fails | Run `dbt deps` and verify `dbt_packages/dbt_cortex_agent/dbt_project.yml` reports the CLI version. A source-root `dbt_project.yml`, branch revision, missing install, or mismatched installed version is not accepted. |
| `init` completed but no Agent exists | Expected: init only appends dependency and selected project vars; author the full-body Agent model, Semantic View, and optional eval model separately. |
| No enabled Agent model | Configure a model with `materialized='cortex_agent'`, explicit naming metadata, and a native YAML body. |
| Semantic model does not resolve | Make the model name unique and materialize it as `semantic_view`. |
| Package macro undefined in model SQL | Call package helpers as `dbt_cortex_agent.<macro>`. |
| Macro call in property YAML fails | Property YAML supports `target`, `var`, and `env_var`, not custom macros. |
| Mutation target rejected | Align CLI `--target`/`--allow-target` with `cortex_agent_deploy_target` and `cortex_agent_allowed_targets`. |
| Database allowlist rejected | Add every manifest-resolved Agent, dependency, stage, evaluation, and result database to the reviewed repeatable `--allow-database` values. `--database` selects connection context; it does not replace resource authorization. |
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
| Controlled error lacks JSON on stdout | Pre-operation configuration/parser errors use stderr/exit `2`. Smoke and durable partial-operation handlers retain their structured evidence on stdout with `--json`; preserve both streams and the exit code. |

## Invocation timeout and failure recovery

Version 0.0.12 adds `--timeout-seconds` to both smoke commands, retaining the
60-second default. Version 0.0.11 has no CLI override. Use an explicit larger
budget only after installing matching 0.0.12 artifacts and approving the call's
cost. Increasing it does not fix
unsupported conclusions or incorrect facts.

1. Save the exit code and complete JSON. Agent smoke retains `response`; skill
   smoke retains prior `verified` skills and `failure.response` in 0.0.12.
2. Distinguish expected-tool mismatch from `response.errors`. A successful
   transport or skill selection does not establish answer quality.
3. For a timeout, inspect elapsed duration, the effective budget and any observed
   request/query identifiers. Do not invent a request ID or assume cancellation.
   Where access permits, read native events scoped to the exact Agent/trace and
   correlate the original question, version and query IDs. Tool SQL completion
   alone does not establish parent Agent completion. Keep content private.
4. If server outcome is unknown, report it as unknown; do not automatically
   invoke again. A recovered answer still does not change the original client
   failure into a pass. Review its facts separately.
5. Approve any new invocation explicitly. Do not retry until green or weaken a
   gate. For deployment partial failures, inspect completed phases and current
   state instead of assuming rollback. For completed evaluation rejection,
   inspect per-row evidence and aggregate floors; baseline acceptance is separate.

See the [CLI reference](reference/cli.md) and [configuration model](guides/configuration-model.md).