# Lifecycle and versioning

dbt owns Cortex Agent DDL and version semantics. The CLI always delegates deploy,
grant, promotion, and rollback to public package macros after producing a fresh
manifest. All lifecycle CLI commands are dry-run unless `--apply` is present.

## Render and dry run

```bash
dbt-cortex-agent agent render --project-dir . --target sandbox \
  --agent orders_assistant --projection canonical --json
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant --allow-target sandbox \
  --allow-database ANALYTICS_DEV --json
```

The equivalent dbt macro path is:

```bash
dbt run-operation cortex_agent__validate --target sandbox \
  --args '{"agent_name":"orders_assistant","projection":"canonical"}'
dbt run-operation cortex_agent__deploy --target sandbox \
  --args '{"agent_name":"orders_assistant","projection":"canonical","dry_run":true}'
```

Render and deploy accept `--projection canonical|native_eval` and default to the
v0.3.0 canonical behavior. Render parses one dbt-owned machine marker, returns
the actual specification and logical/physical identity in human or JSON output,
and writes `<artifact-dir>/renders/<target>/<agent>/<projection>.json`. Missing,
duplicate, malformed, or non-object marker payloads fail closed.

## Preview and run a general Agent smoke

General smoke is separate from skill smoke and works for an Agent with no skills:

```bash
dbt-cortex-agent agent smoke --project-dir . --target sandbox \
  --agent orders_assistant --projection canonical \
  --question "How many orders are in the dataset?" --json
```

The default canonical preview resolves manifest-owned physical identity. An
explicit `--projection native_eval` uses the offline dbt render authority so a
custom evaluation suffix is never guessed. Both report the selected projection
and request without connecting or invoking. To run either, repeat the command with
`--connection`, `--database`, `--schema`, both CLI allowlists, and `--apply`.
`--agent-object` can override the physical object, `--endpoint` can override the
Snowflake endpoint, and `--expect-tool NAME` requires an exact match among the
returned tool-use names. Applied smoke reuses the existing invocation/SSE client;
it does not deploy, alter, commit, alias, grant, upload, or evaluate an Agent.

## Apply in a controlled target

```bash
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant --connection sandbox --database ANALYTICS_DEV \
  --allow-target sandbox --allow-database ANALYTICS_DEV --apply
```

Apply requires all of the following:

- an explicit `--connection` CLI flag,
- a freshly parsed manifest,
- `--database` matching dbt's resolved target database,
- the selected target and database in CLI allowlists,
- the dbt target in `cortex_agent_allowed_targets`,
- the target database in `cortex_agent_allowed_databases`,
- staged `SKILL.md` files for canonical stage-backed skills unless the explicit
  readiness escape hatch is reviewed and disabled.

For `agent deploy --apply`, the CLI discovers all declared skills for the
selected Agents, validates the full upload plan, and uploads them with Snow CLI
before it invokes `cortex_agent__deploy`. Operators do not need a separate
`skill upload --apply` first. The standalone skill command remains useful for
previewing or performing uploads independently.

For `--projection native_eval`, the CLI retains every connection, manifest,
database, allowlist, and macro mutation gate but does not plan or upload skills;
the native-eval specification excludes skills by contract.

The direct macro path is intentionally narrower. It does not run a fresh parse,
require the CLI's explicit `--connection`/resolved-database checks, enforce CLI
allowlists, or upload local skill directories. It does enforce the dbt package's
target/database allowlists and staged-skill readiness. Use direct macros only
when automation already owns manifest freshness, stage upload, connection
context, and capture of dbt logs.

## Deployment sequence

For a changed canonical specification, `cortex_agent__deploy`:

1. validates metadata, projection, target, database, and skill readiness;
2. renders the deterministic specification and hashes it with staged skill state;
3. modifies the LIVE draft;
4. commits an immutable `VERSION$N`;
5. assigns the deploy/requested alias;
6. recreates LIVE from the committed version;
7. optionally attaches enabled MCP servers when MCP deployment is enabled.

An unchanged spec and skill hash skips version churn. If an alias was requested,
the no-change path reconciles it to the current DEFAULT without committing.
Agent-object grants and MCP attachment are separate lifecycle concerns.

## Grant, promote, and roll back

Preview first; repeat with the same safety context and `--apply` only after review:

```bash
dbt-cortex-agent agent grant --agent orders_assistant --target sandbox \
  --allow-target sandbox --allow-database ANALYTICS_DEV
dbt-cortex-agent agent promote --agent orders_assistant --target sandbox \
  --from-alias validated --to-alias production \
  --allow-target sandbox --allow-database ANALYTICS_DEV
dbt-cortex-agent agent rollback --agent orders_assistant --target sandbox \
  --alias production --to-version 'VERSION$2' \
  --allow-target sandbox --allow-database ANALYTICS_DEV
```

Promotion moves an alias already associated with a committed version. Rollback
moves an alias to an explicit immutable version; it does not rewrite history.

Public macro signatures are listed in [macro reference](../reference/macros.md).