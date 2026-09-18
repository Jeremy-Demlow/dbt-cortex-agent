# Cortex Agent integration consumer

This independent dbt project is the release proof fixture for an adopter outside
the package source tree. It contains one seed-backed table, one semantic view,
the normal Orders starter plus two protected-live-only Agent models using the same
physical object name in different databases, and one optional three-row eval suite
covering in-scope, out-of-scope, and negative behavior.

## Proof boundary

The default local path proves:

- dbt package dependency resolution;
- dbt parse and manifest-owned Agent/eval metadata;
- semantic-view/eval compilation when adapter authentication is available;
- package-qualified macros and generic eval coverage tests;
- non-mutating full-Agent rendering and optional evaluation plans;
- installed CLI discovery against this consumer project.
- resource-scoped discovery across two Agent databases and a separate evaluation
  database when the live database variables are supplied.

It does not prove live Agent create/alter/commit, aliases/grants, stage upload,
skill selection, MCP attachment, Snowflake dataset/result creation, or paid Agent
Evaluation. Those require explicit sandbox objects, privileges, credentials,
`--apply`, and spend approval.

The protected package workflow closes the live product boundary with
`scripts/verify_live_multi_database.py`. It installs the exact built wheel,
deploys `SHARED_ASSISTANT` independently in database A and database B, performs
runtime smoke, renders the cross-database eval plan without paid execution, runs
a second no-change build, and retains both database observations plus independent
proof/cleanup outcomes. Runtime and warehouse use can incur costs even with
`paid_evaluation: false`. Separate cleanup-only updates cannot qualify failed or
unattempted proof. The fixture overrides schema naming; default schema generation
is exercised separately by the installed-consumer verifier.
This is package behavior proof, not customer fleet-orchestration proof.

## Local non-mutating proof

Run from this directory:

```bash
dbt deps
dbt parse --profiles-dir .
dbt-cortex-agent doctor --project-dir . --target sandbox --json
dbt-cortex-agent manifest validate --project-dir . --target sandbox \
  --agent orders_assistant --json
dbt compile --project-dir . --profiles-dir . --target sandbox \
  --select orders_assistant
dbt-cortex-agent eval run --project-dir . --target sandbox \
  --agent orders_assistant --suite core --json
```

The Agent-only proof stops after deploy preview and does not require the two
files under `models/agents/orders_assistant/evals/`. The final `eval run` command
is the Agent-plus-eval example; it targets the same physical Agent and does not
deploy another one.

No command above applies mutation or starts evaluation spend. `dbt compile` and
model execution require a valid Snowflake profile; do not treat an offline parse
as proof of live relation or privilege behavior. The checked-in fixture explicitly
allowlists `DBT_CORTEX_AGENT_SANDBOX_A`, `DBT_CORTEX_AGENT_SANDBOX_B`, and
`DBT_CORTEX_AGENT_SANDBOX_EVAL` so its documented `doctor` command validates
the complete fail-closed safety contract; changing the sandbox database requires
changing that allowlist deliberately.

## Optional sandbox configuration

The checked-in profile is environment-driven. Provide approved sandbox values
only when running credentialed dbt operations:

```bash
export SNOWFLAKE_ACCOUNT='<organization-account>'
export SNOWFLAKE_USER='<user>'
export SNOWFLAKE_PRIVATE_KEY_PATH='<absolute-key-path>'
export SNOWFLAKE_ROLE='<sandbox-deploy-role>'
export SNOWFLAKE_WAREHOUSE='<sandbox-warehouse>'
export SNOWFLAKE_DATABASE='DBT_CORTEX_AGENT_SANDBOX_A'
export CORTEX_AGENT_LIVE_DATABASE_A='DBT_CORTEX_AGENT_SANDBOX_A'
export CORTEX_AGENT_LIVE_DATABASE_B='DBT_CORTEX_AGENT_SANDBOX_B'
export CORTEX_AGENT_LIVE_DATABASE_EVAL='DBT_CORTEX_AGENT_SANDBOX_EVAL'
```

The live role also needs access to the pre-provisioned internal stage
`<CORTEX_AGENT_LIVE_DATABASE_EVAL>.EVAL.EVAL_CONFIG_STAGE`.

Before any `--apply`, complete the [Snowflake setup](../docs/getting-started/snowflake-setup.md)
and review [lifecycle](../docs/guides/lifecycle.md) or
[evaluations](../docs/guides/evaluations.md).

See [progressive features](docs/progressive-features.md) only after the minimal
proof boundary is understood.