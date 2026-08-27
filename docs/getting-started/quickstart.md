# Five-minute non-mutating quickstart

This path proves installation, configuration, manifest discovery, and full-body
Agent compilation. It does not upload skills, mutate Snowflake, commit a version,
invoke an Agent, or start a paid evaluation.

## 1. Install and configure

```bash
dbt deps
dbt-cortex-agent --version
dbt-cortex-agent init --project-dir . --target sandbox \
  --allow-target sandbox --allow-database ANALYTICS_DEV
```

The curated Orders tutorial can be previewed with:

```bash
dbt-cortex-agent init --project-dir . --starter orders \
  --package-source https://github.com/Jeremy-Demlow/dbt-cortex-agent.git --json
```

Add `--apply` only after reviewing the exact file actions. The starter includes a
semantic view, one full-body Agent model, and one optional evaluation suite.

## 2. Define an Agent model

Use the [configuration model](../guides/configuration-model.md). Every Agent body
must explicitly declare `models.orchestration`.

## 3. Diagnose and inspect

```bash
dbt-cortex-agent doctor --project-dir . --target sandbox --json
dbt-cortex-agent manifest validate --project-dir . --target sandbox \
  --agent orders_assistant --json
dbt compile --select orders_assistant
```

Resolve every failure before continuing. `dbt compile` renders the full body but
does not invoke the Agent materialization.

## 4. Controlled deployment

The next boundary is package-native deployment. Preview the exact physical
Agent, skill uploads, and dependency selector without connecting:

```bash
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant \
  --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

After review, provide the explicit connection, database, role, and warehouse,
then add `--apply`. The package uploads selected skills and invokes dbt build;
the materialization remains the sole owner of LIVE updates, immutable versions,
aliases, and grants. A Makefile or copied Python wrapper is not required.