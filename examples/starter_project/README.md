# Cortex Agent starter project

This independent Snowflake consumer proves that `dbt_cortex_agent` works outside
the reference ski-resort project.

The minimal graph contains:

- one seed-backed orders table,
- one semantic view,
- one Agent exposure with one Analyst tool,
- one three-row eval suite covering in-scope, out-of-scope, and negative behavior.

## Configure

Set the fail-closed profile values:

```bash
export SNOWFLAKE_ACCOUNT='<organization-account>'
export SNOWFLAKE_USER='<user>'
export SNOWFLAKE_PRIVATE_KEY_PATH='<absolute-key-path>'
export SNOWFLAKE_ROLE='<sandbox-deploy-role>'
export SNOWFLAKE_WAREHOUSE='<sandbox-warehouse>'
export SNOWFLAKE_DATABASE='<sandbox-database>'
```

## Install and compile

Run from this directory:

```bash
dbt deps
dbt parse --profiles-dir .
dbt compile --profiles-dir .
```

## Render without mutation

```bash
dbt run-operation cortex_agent__validate --profiles-dir . \
  --args '{"agent_name":"orders_assistant","projection":"canonical"}'

dbt run-operation cortex_agent__render_spec --profiles-dir . \
  --args '{"agent_name":"orders_assistant","projection":"canonical"}'

dbt run-operation cortex_agent__deploy --profiles-dir . \
  --args '{"agent_name":"orders_assistant","projection":"canonical","dry_run":true}'
```

Do not apply deployment until the database objects and least-privilege roles are
prepared from the package [Snowflake setup guide](../../docs/getting-started/snowflake-setup.md).

See [progressive features](docs/progressive-features.md) only after the minimal path
is understood and verified.
