# Five-minute non-mutating quickstart

This path proves installation, configuration, manifest discovery, rendering, and
the deploy plan locally. It does not upload skills, invoke an Agent, mutate
Snowflake, commit a version, or start a paid evaluation.

## 1. Confirm the two 0.3.1 surfaces

```bash
dbt deps
dbt-cortex-agent --version
```

## 2. Preview explicit safety configuration

If the existing dbt project is not configured, preview dependency and safety-var
additions:

```bash
dbt-cortex-agent init --project-dir . --target sandbox \
  --allow-target sandbox --allow-database ANALYTICS_DEV
```

An existing package dependency is preserved. If none exists, add
`--package-source https://github.com/Jeremy-Demlow/dbt-cortex-agent.git` and
`--revision v0.3.1`. By default, `init` does not create a dbt project or scaffold Agent,
semantic-view, evaluation, seed, or skill files. Do not add `--apply` in this
quickstart.

The one explicit exception is the curated Orders tutorial. Preview its exact
package-owned files and configuration edits with:

```bash
dbt-cortex-agent init --project-dir . --starter orders \
  --package-source https://github.com/Jeremy-Demlow/dbt-cortex-agent.git --json
```

The starter writes only after `--apply`, adds the pinned semantic-view dependency
when absent, preserves an existing declaration, appends the skill exclusion to
`.dbtignore`, leaves identical files unchanged, and rejects differing files
before any write. There is no force option or generic wizard.

## 3. Define one Agent exposure

Use the Agent-only example first, then add the optional eval example only when
ground truth exists, in the [configuration model](../guides/configuration-model.md). The independent
[`integration_tests`](../../integration_tests/README.md) project is an executable
fixture if a consumer project is not ready.

## 4. Diagnose and inspect the resolved graph

```bash
dbt-cortex-agent doctor --project-dir . --target sandbox --json
dbt-cortex-agent manifest validate --project-dir . --target sandbox --agent orders_assistant --json
```

Both commands run a fresh `dbt parse` before reading `target/manifest.json`.
Resolve every doctor failure before continuing. For an immutable SHA dependency,
doctor requires the matching installed consumer package metadata produced by
`dbt deps`; it does not accept this package repository's root metadata as a
substitute.

## 5. Render and dry-run deployment

```bash
dbt-cortex-agent agent render --project-dir . --target sandbox --agent orders_assistant --json
dbt-cortex-agent agent deploy --project-dir . --target sandbox --agent orders_assistant --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

No command above contains `--apply`. The next boundary is a
[controlled deploy](../guides/lifecycle.md), which requires Snowflake setup,
an explicit connection, a matching database, both allowlists, and deliberate
operator approval.