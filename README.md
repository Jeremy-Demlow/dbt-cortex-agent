# dbt_cortex_agent

`dbt_cortex_agent` 0.3.0 is a Snowflake-only dbt package and Python CLI for
defining, validating, rendering, versioning, and evaluating Cortex Agents from
dbt metadata. Agents are dbt exposures; semantic views and evaluation datasets
remain dbt models. dbt owns the specification and lifecycle macros, while the
CLI consumes `target/manifest.json`, delegates Agent changes to those macros,
and manages local files, runtime clients, and evaluation artifacts.

## Install one version on two surfaces

Pin the dbt package to the `v0.3.0` Git revision in `packages.yml`:

```yaml
packages:
  - git: "git@github.com:Jeremy-Demlow/dbt-cortex-agent.git"
    revision: v0.3.0
```

Install the matching wheel from the approved release source or private index:

```bash
dbt deps
python -m pip install 'dbt-cortex-agent==0.3.0'
```

Use `dbt-cortex-agent[runtime]==0.3.0` only for connector-backed skill smoke
or paid evaluation. The supported runtime is Python `>=3.10,<4`, dbt
`>=1.10,<2.0`, and `dbt-snowflake`; see [compatibility](docs/reference/compatibility.md)
and [installation](docs/getting-started/installation.md).

## Five-minute non-mutating quickstart

From a consumer dbt project with an Agent exposure:

```bash
dbt-cortex-agent doctor --project-dir . --target sandbox --json
dbt-cortex-agent manifest validate --project-dir . --target sandbox --json
dbt-cortex-agent agent render --project-dir . --target sandbox --agent orders_assistant --json
dbt-cortex-agent agent deploy --project-dir . --target sandbox --agent orders_assistant \
  --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

These commands run a fresh `dbt parse`; none uses `--apply`. The final command
renders the controlled deploy path without mutating Snowflake. Follow the
[quickstart](docs/getting-started/quickstart.md) to create the metadata and
bootstrap explicit allowlists.

## Controlled deploy

Review the dry run, use an isolated target/database, then opt in explicitly:

```bash
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant --connection sandbox --database ANALYTICS_DEV \
  --allow-target sandbox --allow-database ANALYTICS_DEV --apply
```

`--apply` requires an explicit `--connection`; the configured database must
match dbt's resolved target, and the target/database must pass both CLI and dbt
allowlists. Deployment updates LIVE, commits `VERSION$N`, and may move an alias.
Read [lifecycle](docs/guides/lifecycle.md) and [Snowflake setup](docs/getting-started/snowflake-setup.md)
before crossing this boundary.

## CLI or dbt macros

| Need | Shipped CLI | Public dbt macro |
|---|---|---|
| Diagnose a project | `doctor` | — |
| Validate resolved metadata | `manifest validate` | `cortex_agent__validate` |
| Render canonical specs | `agent render` | `cortex_agent__render_spec` |
| Deploy/version an Agent | `agent deploy` | `cortex_agent__deploy` |
| Grant, promote, roll back | `agent grant/promote/rollback` | lifecycle macros |
| Plan/upload/smoke skills | `skill plan/upload/smoke` | deploy validates staged skills |
| Render/run native evaluation | `eval run` | `cortex_eval__execution_plan`, `cortex_eval__run` |
| Compare/gate/accept artifacts | `eval compare/gate/accept-baseline` | threshold macros only |

Use macros inside dbt-native automation. Use the CLI when local file upload,
stable process exits/JSON, connector clients, or durable evaluation artifacts
are required. Both paths consume the same dbt metadata; Python does not own a
second Agent DDL implementation.

## Lifecycle and evaluation

Canonical deploy validates and hashes the rendered spec plus staged skills,
skips unchanged versions, modifies LIVE, commits an immutable version, and
applies the requested alias. Promotion, rollback, grants, MCP attachment, and
skill smoke remain explicit operations.

Native evaluation uses a separate suffixed Agent rendered from the same exposure
without unsupported skills or MCP connectors. `eval run` is a client for an
already deployed native-eval Agent, materialized eval table, and evaluation
stage; `--apply` incurs Cortex spend. It writes candidate JSON with plan identity,
ordered ground-truth refs, policy, and pre/post DEFAULT provenance for threshold
and accepted-baseline gates. See [evaluations](docs/guides/evaluations.md).

## Documentation

- Start: [installation](docs/getting-started/installation.md), [quickstart](docs/getting-started/quickstart.md), [Snowflake setup](docs/getting-started/snowflake-setup.md)
- Configure: [configuration model](docs/guides/configuration-model.md), [Agent metadata](docs/reference/agent-metadata.md), [eval metadata](docs/reference/eval-metadata.md), [variables](docs/reference/variables.md)
- Operate: [lifecycle](docs/guides/lifecycle.md), [skills](docs/guides/skills.md), [evaluations](docs/guides/evaluations.md), [CI](docs/guides/ci.md)
- Reference: [CLI](docs/reference/cli.md), [macros](docs/reference/macros.md), [compatibility](docs/reference/compatibility.md), [architecture](docs/concepts/end-to-end-flow.md), [troubleshooting](docs/troubleshooting.md)
- Change: [upgrade from v0.2.0](UPGRADING.md), [changelog](CHANGELOG.md)

## Limitations and policies

- Snowflake and dbt Core with `dbt-snowflake` are the release authority; DuckDB is unsupported and Fusion is advisory.
- `dbt run` does not deploy exposures. Agent lifecycle requires explicit CLI commands or `dbt run-operation` macros.
- Property YAML may use `target`, `var`, and `env_var`, but cannot call package macros.
- Skills and MCP connectors are excluded from built-in native Agent Evaluation and require separate smoke/integration proof.
- Live mutation, runtime smoke, and evaluation spend are never default operations.
- This independent package is not sponsored, endorsed, supported, or maintained by Snowflake Inc. Public publication remains subject to [governance](GOVERNANCE.md), [maintainer](MAINTAINERS.md), and legal-review gates.

Apache License 2.0. See [LICENSE](LICENSE), [contributing](CONTRIBUTING.md),
[security](SECURITY.md), [support](SUPPORT.md), and [Code of Conduct](CODE_OF_CONDUCT.md).