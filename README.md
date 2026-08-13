# dbt_cortex_agent

`dbt_cortex_agent` 0.3.1 is a Snowflake-only dbt package and Python CLI for
defining, versioning, and evaluating Cortex Agents from dbt models. A
`materialized='cortex_agent'` model body is the native Agent YAML specification.
dbt owns Agent creation and immutable version lifecycle; the CLI consumes
`target/manifest.json` and manages local skills, runtime clients, and evaluation
artifacts. Legacy exposure declarations remain supported during migration.

## Install one immutable version on two surfaces

Version 0.3.1 is not published to PyPI yet. Install the reviewed Python CLI and
runtime support from a clean local checkout:

```bash
pipx install '/absolute/path/to/dbt-cortex-agent[runtime]'
```

For a managed Python environment, use:

```bash
python -m pip install '/absolute/path/to/dbt-cortex-agent[runtime]'
```

dbt does not install packages from PyPI. Pin the dbt package separately to the
public HTTPS `v0.3.1` Git tag in `packages.yml`:

```yaml
packages:
  - git: "https://github.com/Jeremy-Demlow/dbt-cortex-agent.git"
    revision: v0.3.1
```

The future PyPI version `0.3.1` and Git tag `v0.3.1` will identify the same immutable
release across the CLI and dbt surfaces. Run `dbt deps`, then
`dbt-cortex-agent doctor --project-dir . --json`; `doctor` verifies that the CLI,
declared dbt dependency, and installed consumer dbt package versions align. A
full immutable Git SHA is accepted only when actual installed package metadata
under `dbt_packages/dbt_cortex_agent` reports the matching version; a source
checkout's root `dbt_project.yml` is not installation evidence. The supported
runtime is Python `>=3.10,<4`, dbt
`>=1.10,<2.0`, and `dbt-snowflake`; see [compatibility](docs/reference/compatibility.md)
and [installation](docs/getting-started/installation.md).

The CLI also requires the Snowflake CLI (`snow`) on `PATH`; `doctor` checks both
the `dbt` and `snow` executables. By default, `dbt-cortex-agent init` configures an existing
dbt project by appending missing dependency and safety-variable entries. It does
not create a dbt project or scaffold Agent models, semantic views, evaluation
models, seeds, or skill files.

For the fixed synthetic tutorial, preview the package-owned Orders starter in an
existing dbt project:

```bash
dbt-cortex-agent init --project-dir . --starter orders \
  --package-source https://github.com/Jeremy-Demlow/dbt-cortex-agent.git --json
```

The preview reports the exact seed, semantic-view, Agent, optional eval, dependency, and
`.dbtignore` actions without writing. After review, add `--apply`. The command
validates every destination before writing, keeps identical files unchanged,
and fails closed if any generated file already has different content. It has no
force mode and is not a generic project or Agent wizard.

## Five-minute non-mutating quickstart

From a consumer dbt project with a full-body Agent model:

```bash
dbt-cortex-agent doctor --project-dir . --target sandbox --json
dbt-cortex-agent manifest validate --project-dir . --target sandbox --json
dbt compile --select orders_assistant
```

These commands do not mutate Snowflake. `dbt compile` renders and validates the
full Agent body without invoking its materialization. Follow the
[quickstart](docs/getting-started/quickstart.md) to create the metadata and
bootstrap explicit allowlists.

For Cortex Code-guided adoption, use the project-local
[`dbt-cortex-agent-project` skill](.cortex/skills/dbt-cortex-agent-project/SKILL.md).
It discovers an existing dbt project, establishes objective/levers/data/proof,
and guides an existing semantic view, the fixed Orders starter, or an existing
Agent into dbt-owned metadata. It is script-free, shows manual 0.3.1 command
parity, and stops separately before local writes, Snowflake mutation/runtime,
paid evaluation, and baseline movement. The checked-in skill is not a claim of
catalog publication or live Snowflake verification.

## Controlled deploy

Upload declared skills, use an isolated target/database, then build explicitly:

```bash
dbt-cortex-agent skill upload --project-dir . --target sandbox \
  --agent orders_assistant --connection sandbox --database ANALYTICS_DEV \
  --allow-target sandbox --allow-database ANALYTICS_DEV --apply
dbt build --select orders_assistant
```

The model relation determines the physical Agent FQN. The model body is passed
directly to the materialization, which validates explicit orchestration, checks
staged skills, updates LIVE, commits immutable `VERSION$N`, and reconciles the
configured alias. Skill upload remains a separate Python responsibility and
must succeed before `dbt build`.
Read [lifecycle](docs/guides/lifecycle.md) and [Snowflake setup](docs/getting-started/snowflake-setup.md)
before crossing this boundary.

## CLI or dbt macros

| Need | Shipped CLI | Public dbt macro |
|---|---|---|
| Diagnose a project | `doctor` | — |
| Validate resolved metadata | `manifest validate` | `cortex_agent__validate` |
| Render the full Agent spec | — | `dbt compile --select <agent_model>` |
| Deploy/version an Agent | — | `dbt build --select <agent_model>` |
| Preview/invoke any Agent | `agent smoke` | — |
| Grant, promote, roll back | `agent grant/promote/rollback` | lifecycle macros |
| Plan/upload/smoke skills | `skill plan/upload/smoke` | deploy validates staged skills |
| Render/run optional evaluation | `eval run` | `cortex_eval__execution_plan`, `cortex_eval__run` |
| Compare/gate/accept artifacts | `eval compare/gate/accept-baseline` | threshold macros only |

Use dbt for model Agent render/deploy. Use the CLI when local file upload,
stable process exits/JSON, connector clients, or durable evaluation artifacts
are required. Python does not own a second Agent DDL implementation. Legacy
exposure Agents retain the older render/deploy commands during migration.

## Lifecycle and evaluation

Agent deploy validates and hashes the rendered spec plus staged skills,
skips unchanged versions, modifies LIVE, commits an immutable version, and
applies the requested alias. Promotion, rollback, grants, MCP attachment, and
skill smoke remain explicit operations.

Evaluation is optional and targets the same Agent selected by the model relation.
`eval run` is a client for that already deployed Agent, a materialized
eval table, and an evaluation stage; `--apply` incurs Cortex spend. It never
deploys or changes an Agent. It writes candidate JSON with plan identity,
ordered ground-truth refs, policy, and pre/post DEFAULT provenance for threshold
and accepted-baseline gates. See [evaluations](docs/guides/evaluations.md).

## Documentation

- Start: [installation](docs/getting-started/installation.md), [quickstart](docs/getting-started/quickstart.md), [Snowflake setup](docs/getting-started/snowflake-setup.md)
- Configure: [configuration model](docs/guides/configuration-model.md), [Agent metadata](docs/reference/agent-metadata.md), [eval metadata](docs/reference/eval-metadata.md), [variables](docs/reference/variables.md)
- Operate: [lifecycle](docs/guides/lifecycle.md), [skills](docs/guides/skills.md), [evaluations](docs/guides/evaluations.md), [CI](docs/guides/ci.md), [releasing](docs/guides/releasing.md)
- Reference: [CLI](docs/reference/cli.md), [macros](docs/reference/macros.md), [compatibility](docs/reference/compatibility.md), [architecture](docs/concepts/end-to-end-flow.md), [troubleshooting](docs/troubleshooting.md)
- Change: [upgrade to v0.3.1](UPGRADING.md), [changelog](CHANGELOG.md)

## Limitations and policies

- Snowflake and dbt Core with `dbt-snowflake` are the release authority; DuckDB is unsupported and Fusion is advisory.
- `dbt build --select <agent_model>` deploys model Agents; `dbt compile` is the non-mutating preview.
- Property YAML may use `target`, `var`, and `env_var`, but cannot call package macros.
- Skills and MCP connectors are excluded from built-in native Agent Evaluation and require separate smoke/integration proof.
- Live mutation, runtime smoke, and evaluation spend are never default operations.
- This independent, maintainer-led package is not sponsored, endorsed, supported, or maintained by Snowflake Inc.

Apache License 2.0. See [LICENSE](LICENSE), [contributing](CONTRIBUTING.md),
[security](SECURITY.md), [support](SUPPORT.md), and [Code of Conduct](CODE_OF_CONDUCT.md).