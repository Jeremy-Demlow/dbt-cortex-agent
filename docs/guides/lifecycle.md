# Lifecycle and versioning

dbt owns Cortex Agent DDL and version semantics. Python owns planning, local
skill upload, runtime smoke, and evaluation coordination. Package lifecycle
commands delegate mutation to dbt macros.

## Compile before mutation

```bash
dbt deps --project-dir .
dbt parse --project-dir . --profiles-dir . --target sandbox
dbt compile --project-dir . --profiles-dir . --target sandbox \
  --select orders_assistant
```

Compile renders and validates the full native Agent YAML without invoking the
custom materialization or connecting to Snowflake.

## Use package-native deployment

Preview the complete operation first:

```bash
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant \
  --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

After review, provide the approved execution context and apply:

```bash
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant --connection sandbox --database ANALYTICS_DEV \
  --role AGENT_DEPLOYER --warehouse AGENT_WH \
  --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
```

The package runs a fresh parse, resolves the physical Agent and dependency
closure, preflights and uploads declared skills, and invokes dbt build. The
project must configure non-empty
`cortex_agent_allowed_targets` and `cortex_agent_allowed_databases`, and the
selected target/database must match them. Stage-backed skills must already have
valid local `SKILL.md` files and an existing configured stage.

Direct `skill plan`, `skill upload`, and `dbt build --select +orders_assistant`
remain lower-level primitives for operators who deliberately own their own
sequencing. They are not required for the normal adopter path, and a wrapper
must not recreate package deployment behavior.

## Materialization sequence

For a changed full specification, the `cortex_agent` materialization:

1. validates the rendered YAML mapping and explicit orchestration;
2. derives the physical FQN from the dbt model relation;
3. enforces target, database, and staged-skill readiness;
4. hashes the deterministic specification and staged skill state;
5. creates `VERSION$1` directly from the first specification, or modifies LIVE
   and commits one later immutable `VERSION$N` when content changed;
6. reconciles the requested alias, profile, and comment;
7. recreates LIVE from the committed version and returns no fake relation.

An unchanged spec and skill hash skips version churn by finding the newest
matching managed version independently of serving DEFAULT. This remains true
after rollback.

## Smoke is a separate runtime boundary

```bash
dbt-cortex-agent agent smoke --project-dir . --target sandbox \
  --agent orders_assistant \
  --question "How many orders are in the dataset?" --json
```

Preview resolves the physical identity without invoking it. Add the explicit
connection, database/schema, allowlists, and `--apply` only for an approved live
runtime check. Smoke never deploys or changes an Agent.

Use `agent versions`, `agent promote`, and `agent rollback` for explicit routing.
Alias movement does not change DEFAULT unless `--set-default` is supplied. Use
`agent drop` only for deliberately confirmed retirement; dbt model removal does
not delete an Agent.

Alias reassignment is two durable Snowflake statements: the current owner is
unset before the target version receives the alias. The package rejects stale
observed state, verifies the final owner, and reports partial state if either
statement fails. Snowflake does not provide an atomic compare-and-swap for this
operation, so conflicting operators must retry from freshly inspected state.