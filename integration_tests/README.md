# Cortex Agent integration consumer

This independent dbt project is the release proof fixture for an adopter outside
the package source tree. It contains one seed-backed table, one semantic view,
one Agent exposure with an Analyst tool, and one three-row eval suite covering
in-scope, out-of-scope, and negative behavior.

## Proof boundary

The default local path proves:

- dbt package dependency resolution;
- dbt parse and manifest-owned Agent/eval metadata;
- semantic-view/eval compilation when adapter authentication is available;
- package-qualified macros and generic eval coverage tests;
- non-mutating canonical and native-eval rendering/execution plans;
- installed CLI discovery against this consumer project.

It does not prove live Agent create/alter/commit, aliases/grants, stage upload,
skill selection, MCP attachment, Snowflake dataset/result creation, or paid Agent
Evaluation. Those require explicit sandbox objects, privileges, credentials,
`--apply`, and spend approval.

## Local non-mutating proof

Run from this directory:

```bash
dbt deps
dbt parse --profiles-dir .
dbt-cortex-agent doctor --project-dir . --target sandbox --json
dbt-cortex-agent manifest validate --project-dir . --target sandbox \
  --agent orders_assistant --json
dbt-cortex-agent agent render --project-dir . --target sandbox \
  --agent orders_assistant --json
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant --allow-target sandbox \
  --allow-database AM_SKI_RESORT_DBT_FOCUS --json
dbt-cortex-agent eval run --project-dir . --target sandbox \
  --agent orders_assistant --suite core --json
```

No command above applies mutation or starts evaluation spend. `dbt compile` and
model execution require a valid Snowflake profile; do not treat an offline parse
as proof of live relation or privilege behavior.

## Optional sandbox configuration

The checked-in profile is environment-driven. Provide approved sandbox values
only when running credentialed dbt operations:

```bash
export SNOWFLAKE_ACCOUNT='<organization-account>'
export SNOWFLAKE_USER='<user>'
export SNOWFLAKE_PRIVATE_KEY_PATH='<absolute-key-path>'
export SNOWFLAKE_ROLE='<sandbox-deploy-role>'
export SNOWFLAKE_WAREHOUSE='<sandbox-warehouse>'
export SNOWFLAKE_DATABASE='AM_SKI_RESORT_DBT_FOCUS'
```

Before any `--apply`, complete the [Snowflake setup](../docs/getting-started/snowflake-setup.md)
and review [lifecycle](../docs/guides/lifecycle.md) or
[evaluations](../docs/guides/evaluations.md).

See [progressive features](docs/progressive-features.md) only after the minimal
proof boundary is understood.