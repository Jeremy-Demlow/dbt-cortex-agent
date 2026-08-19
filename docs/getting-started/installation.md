# Installation

Version 0.0.2 has two install surfaces with one immutable release identity: the dbt package
provides metadata contracts and macros; the Python distribution provides the
`dbt-cortex-agent` CLI. Pin both to 0.0.2.

## 1. Install the dbt package

dbt does not install packages from PyPI. Add the public HTTPS Git tag to the
consumer project's `packages.yml`:

```yaml
packages:
  - git: "https://github.com/Jeremy-Demlow/dbt-cortex-agent.git"
    revision: v0.0.2
```

There is no dbt Hub coordinate in 0.0.2. Use the immutable tag, not a branch.
For local package development only,
replace the Git declaration with an explicit `local:` path.

Analyst tools also require a compatible semantic-view package, such as:

```yaml
packages:
  - git: "https://github.com/Jeremy-Demlow/dbt-cortex-agent.git"
    revision: v0.0.2
  - package: Snowflake-Labs/dbt_semantic_view
    version: 1.0.5
```

Install dependencies:

```bash
dbt deps
dbt parse
```

## 2. Install Snow CLI

Install the Snowflake CLI so the `snow` executable is on `PATH`. The package
uses it for connection diagnostics and stage uploads. A custom executable can be
selected with `--snow-executable` or `SNOW_EXECUTABLE`.

## 3. Install the Python CLI

Install the CLI and connector-backed runtime support from PyPI:

```bash
pipx install 'dbt-cortex-agent[runtime]==0.0.2'
dbt-cortex-agent --version
```

For a managed Python environment, the pip equivalent is:

```bash
python -m pip install 'dbt-cortex-agent[runtime]==0.0.2'
```

The base distribution can omit `[runtime]` when connector-backed skill smoke and
paid evaluation are not needed. `runtime` is the only connector extra; the
former `invoke` and `eval` extras no longer exist; both map to `runtime`.

The PyPI version `0.0.2` and Git tag `v0.0.2` identify the same immutable
release. After `dbt deps`, run `dbt-cortex-agent doctor --project-dir . --json`.
`doctor` compares the CLI version with the declared dependency revision and the
installed consumer dbt package version so mixed releases fail visibly. A full
40-character Git SHA is accepted only when
`dbt_packages/dbt_cortex_agent/dbt_project.yml` reports version `0.0.2`; the
package source root is not installation evidence. Branch revisions and missing
or mismatched installed metadata fail closed. A semantic `v0.0.2` declaration
continues to match the CLI version directly.

## 4. Configure an existing dbt project

Preview changes first. A new package declaration requires an explicit source,
and deployment configuration requires a target plus at least one allowed database:

```bash
dbt-cortex-agent init --project-dir . \
  --package-source 'https://github.com/Jeremy-Demlow/dbt-cortex-agent.git' \
  --revision v0.0.2 --target sandbox --allow-target sandbox \
  --allow-database ANALYTICS_DEV --agent-schema AGENTS --eval-schema EVAL
```

If an exact dependency already exists, init preserves it. Preview output writes
nothing. After review, repeat with `--apply`; add `--run-dbt-deps` only when the
CLI should run dependency installation after writing. Init appends missing
top-level entries without replacing existing values.

By default, `init` is a configuration helper, not a scaffold command. The destination must
already be a dbt project with `dbt_project.yml`. It can append a missing package
declaration and selected top-level safety/schema variables, but it does not
create Agent exposure YAML, semantic-view models, evaluation models, seeds,
skills, profiles, or a new dbt project. The explicit `--starter orders` option is
the only curated exception: it adds the fixed package-owned Orders tutorial to
the existing project after collision-safe preview.

Continue with the [quickstart](quickstart.md). Review [compatibility](../reference/compatibility.md)
and [upgrade guidance](../../UPGRADING.md) before changing an existing installation.