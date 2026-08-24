# Lifecycle and versioning

dbt owns Cortex Agent DDL and version semantics. Python owns local skill upload,
runtime smoke, and evaluation coordination; it exposes no Agent render, deploy,
grant, promote, or rollback commands.

## Compile before mutation

```bash
dbt deps --project-dir .
dbt parse --project-dir . --profiles-dir . --target sandbox
dbt compile --project-dir . --profiles-dir . --target sandbox \
  --select orders_assistant
```

Compile renders and validates the full native Agent YAML without invoking the
custom materialization or connecting to Snowflake.

## Upload skills, then build

Preview and upload declared skills separately:

```bash
dbt-cortex-agent skill plan --project-dir . --target sandbox \
  --agent orders_assistant --json
dbt-cortex-agent skill upload --project-dir . --target sandbox \
  --agent orders_assistant --connection sandbox --database ANALYTICS_DEV \
  --allow-target sandbox --allow-database ANALYTICS_DEV --apply
```

After review, execute the Agent model and its dependencies:

```bash
dbt build --project-dir . --profiles-dir . --target sandbox \
  --select +orders_assistant
```

Build requires a profile that resolves the approved database, schema, role, and
warehouse. The project must configure non-empty
`cortex_agent_allowed_targets` and `cortex_agent_allowed_databases`, and the
selected target/database must match them. Stage-backed skills must already have
their `SKILL.md` files on the configured stage.

## Materialization sequence

For a changed full specification, the `cortex_agent` materialization:

1. validates the rendered YAML mapping and explicit orchestration;
2. derives the physical FQN from the dbt model relation;
3. enforces target, database, and staged-skill readiness;
4. hashes the deterministic specification and staged skill state;
5. modifies the LIVE draft and commits an immutable `VERSION$N`;
6. reconciles the requested alias, profile, and comment;
7. recreates LIVE from the committed version and returns no fake relation.

An unchanged spec and skill hash skips version churn. Alias drift can be
reconciled without creating another immutable version.

## Smoke is a separate runtime boundary

```bash
dbt-cortex-agent agent smoke --project-dir . --target sandbox \
  --agent orders_assistant \
  --question "How many orders are in the dataset?" --json
```

Preview resolves the physical identity without invoking it. Add the explicit
connection, database/schema, allowlists, and `--apply` only for an approved live
runtime check. Smoke never deploys or changes an Agent.

Explicit alias, grant, and rollback macros are listed in the
[macro reference](../reference/macros.md). They are post-build operations for
automation that already owns dbt profile context and safety approval; they are
not Python CLI commands.