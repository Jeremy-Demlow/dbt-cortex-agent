# Installation

Version 0.3.0 has two install surfaces with one immutable release identity: the dbt package
provides metadata contracts and macros; the Python distribution provides the
`dbt-cortex-agent` CLI. Pin both to 0.3.0.

## 1. Install the dbt package

dbt does not install packages from PyPI. Add the public HTTPS Git tag to the
consumer project's `packages.yml`:

```yaml
packages:
  - git: "https://github.com/Jeremy-Demlow/dbt-cortex-agent.git"
    revision: v0.3.0
```

There is no dbt Hub coordinate in 0.3.0. Use the immutable tag, not a branch.
For local package development only,
replace the Git declaration with an explicit `local:` path.

Analyst tools also require a compatible semantic-view package, such as:

```yaml
packages:
  - git: "https://github.com/Jeremy-Demlow/dbt-cortex-agent.git"
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

After v0.3.0 is published to PyPI, install the CLI and its connector-backed
runtime support with `pipx`:

```bash
pipx install 'dbt-cortex-agent[runtime]==0.3.0'
dbt-cortex-agent --version
```

For a managed Python environment, the pip equivalent is:

```bash
python -m pip install 'dbt-cortex-agent[runtime]==0.3.0'
```

The PyPI commands above become available only after the v0.3.0 publication.
Before publication, environments that can access the repository can install the
current source snapshot pinned to commit `7027d45613423e90a522a8e1ec283c6ce56f33bc`:

```bash
pipx install 'dbt-cortex-agent[runtime] @ git+https://github.com/Jeremy-Demlow/dbt-cortex-agent.git@7027d45613423e90a522a8e1ec283c6ce56f33bc'
```

The base distribution can omit `[runtime]` when connector-backed skill smoke and
paid evaluation are not needed. `runtime` is the only connector extra; the
former `invoke` and `eval` extras no longer exist; both map to `runtime`.

The PyPI version `0.3.0` and Git tag `v0.3.0` identify the same immutable
release. After `dbt deps`, run `dbt-cortex-agent doctor --project-dir . --json`.
`doctor` compares the CLI version with the declared dependency revision and the
installed dbt package version so mixed releases fail visibly.

## 3. Bootstrap explicit project configuration

Preview changes first. A new package declaration requires an explicit source,
and deployment configuration requires a target plus at least one allowed database:

```bash
dbt-cortex-agent init --project-dir . \
  --package-source 'https://github.com/Jeremy-Demlow/dbt-cortex-agent.git' \
  --revision v0.3.0 --target sandbox --allow-target sandbox \
  --allow-database ANALYTICS_DEV --agent-schema AGENTS --eval-schema EVAL
```

If an exact dependency already exists, init preserves it. Preview output writes
nothing. After review, repeat with `--apply`; add `--run-dbt-deps` only when the
CLI should run dependency installation after writing. Init appends missing
top-level entries without replacing existing values.

Continue with the [quickstart](quickstart.md). Review [compatibility](../reference/compatibility.md)
and [upgrade guidance](../../UPGRADING.md) before changing an existing installation.