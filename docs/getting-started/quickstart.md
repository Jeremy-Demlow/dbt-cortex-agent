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

The next boundary is the controlled deployment guide. Upload staged skills with
explicit apply approval, then run `dbt build --select orders_assistant`. The
materialization validates allowlists and staged skills, updates LIVE, commits an
immutable version, and reconciles the configured alias.