# Installation

Version 0.3.0 has two install surfaces with one release identity: the dbt package
provides metadata contracts and macros; the Python distribution provides the
`dbt-cortex-agent` CLI. Pin both to 0.3.0.

## 1. Install the dbt package

Add the private Git release to the consumer project's `packages.yml`:

```yaml
packages:
  - git: "git@github.com:Jeremy-Demlow/dbt-cortex-agent.git"
    revision: v0.3.0
```

The environment must have repository access. There is no dbt Hub coordinate in
0.3.0. Use an immutable tag, not a branch. For local package development only,
replace the Git declaration with an explicit `local:` path.

Analyst tools also require a compatible semantic-view package, such as:

```yaml
packages:
  - git: "git@github.com:Jeremy-Demlow/dbt-cortex-agent.git"
    revision: v0.3.0
  - package: Snowflake-Labs/dbt_semantic_view
    version: 1.0.5
```

Install dependencies:

```bash
dbt deps
dbt parse
```

## 2. Install the Python CLI

Install the companion from the approved v0.3.0 wheel or configured private Python
index. The base distribution supports bootstrap, doctor, manifest inspection,
Agent macro coordination, skill planning/upload through Snow CLI, and local
artifact gates:

```bash
python -m pip install 'dbt-cortex-agent==0.3.0'
dbt-cortex-agent --version
```

Install the single runtime extra when connector-backed skill smoke or paid
evaluation execution is needed:

```bash
python -m pip install 'dbt-cortex-agent[runtime]==0.3.0'
```

The former `invoke` and `eval` extras no longer exist; both map to `runtime`.

## 3. Bootstrap explicit project configuration

Preview changes first. A new package declaration requires an explicit source,
and deployment configuration requires a target plus at least one allowed database:

```bash
dbt-cortex-agent init --project-dir . \
  --package-source 'git@github.com:Jeremy-Demlow/dbt-cortex-agent.git' \
  --revision v0.3.0 --target sandbox --allow-target sandbox \
  --allow-database ANALYTICS_DEV --agent-schema AGENTS --eval-schema EVAL
```

If an exact dependency already exists, init preserves it. Preview output writes
nothing. After review, repeat with `--apply`; add `--run-dbt-deps` only when the
CLI should run dependency installation after writing. Init appends missing
top-level entries without replacing existing values.

Continue with the [quickstart](quickstart.md). Review [compatibility](../reference/compatibility.md)
and [upgrade guidance](../../UPGRADING.md) before changing an existing installation.