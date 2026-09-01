# dbt-cortex-agent documentation

`dbt-cortex-agent` has two coordinated surfaces: a dbt package that owns
declarative Cortex Agent state and mutating Agent DDL, and a Python CLI that
owns reusable planning, orchestration, runtime calls, evaluation, and evidence.

> **dbt is the system of record. The manifest is the contract. Layout is
> convention.**

Use this index to follow one canonical path through the package. Pages under
`getting-started` teach the first successful workflow, guides explain complete
operations, concepts explain design decisions, and references define exact
interfaces.

## Start here

1. [Install one coordinated release](getting-started/installation.md).
2. [Configure Snowflake prerequisites](getting-started/snowflake-setup.md).
3. [Complete the non-mutating quickstart](getting-started/quickstart.md).
4. [Build your first Agent](getting-started/first-agent.md).
5. [Follow the end-to-end developer and CI/CD workflow](guides/developer-ci-workflow.md).

## Guides

- [Configuration model](guides/configuration-model.md) - author a full-body
  Agent model and declare its dbt dependencies.
- [Lifecycle and versioning](guides/lifecycle.md) - understand LIVE, immutable
  versions, aliases, DEFAULT, rollback, and retirement.
- [Skills](guides/skills.md) - declare, upload, and prove stage-backed skills.
- [Evaluations](guides/evaluations.md) - author SQL-computed ground truth, run
  native evaluation, gate candidates, and accept baselines.
- [Access control](guides/access-control.md) - separate deployment, runtime,
  evaluation, and infrastructure privileges.
- [MCP](guides/mcp.md) - understand the current MCP ownership boundary.
- [CI](guides/ci.md) - split offline pull-request proof from approved live work.
- [Troubleshooting](troubleshooting.md) - diagnose failures from current state.

## Concepts

- [End-to-end architecture](concepts/end-to-end-flow.md) - trace authoring,
  manifest resolution, deployment, runtime, and evaluation.
- [dbt and Python ownership](concepts/ownership-boundary.md) - identify the
  authority for each lifecycle operation.
- [Lifecycle-era architecture](concepts/exposure-architecture.md) - understand
  the current model-based architecture and its history.
- [Single-Agent capability proof](concepts/single-agent-capability-proof.md) -
  distinguish Agent identity from capability-specific proof.

## Reference

- [CLI](reference/cli.md) - commands, options, outputs, and exit behavior.
- [Agent model and metadata](reference/agent-metadata.md) - full-body model,
  relation identity, and lifecycle metadata.
- [Evaluation metadata](reference/eval-metadata.md) - evaluation ownership and
  suite schema.
- [Project variables](reference/variables.md) - dbt configuration variables.
- [Macros](reference/macros.md) - public and delegated dbt macro interfaces.
- [Compatibility](reference/compatibility.md) - supported Python, dbt, and
  Snowflake surfaces.

## Maintainers and policy

- [Release workflow](guides/releasing.md) - qualify and publish matching Python
  and dbt release coordinates.
- [Public content policy](public-content-policy.md) - keep the repository safe
  to publish.
- [Contributing](../CONTRIBUTING.md) - development and review expectations.
- [Changelog](../CHANGELOG.md) - released behavior by version.

The repository-local Cortex Code skill is a maintainer convenience, not a
requirement for adopters. Every supported adopter workflow has direct `dbt` or
`dbt-cortex-agent` command parity.