# dbt_cortex_agent

`dbt_cortex_agent` 0.0.8 is a Snowflake-only dbt package and Python companion for
defining, versioning, evaluating, and operating Cortex Agents from dbt models.
A `materialized='cortex_agent'` model body is the native Agent YAML
specification.

> **dbt is the system of record. The manifest is the contract. Layout is
> convention.**

dbt owns Agent intent, dependency state, physical identity, and every mutating
`CREATE AGENT`, `ALTER AGENT`, and `DROP AGENT` statement. The direct
`dbt-cortex-agent` CLI is the reusable operator interface: it generates a fresh
manifest, plans bounded operations, uploads local skill files, delegates Agent
DDL to dbt, invokes the runtime API, coordinates evaluation, and retains
evidence. It does not implement a second Agent specification or DDL authority.

## Install one immutable version on two surfaces

Install the Python companion from PyPI:

```bash
pipx install 'dbt-cortex-agent[runtime]==0.0.8'
```

For a managed Python environment, use:

```bash
python -m pip install 'dbt-cortex-agent[runtime]==0.0.8'
```

dbt does not install packages from PyPI. Pin the dbt package separately to the
public HTTPS `v0.0.8` Git tag in `packages.yml`:

```yaml
packages:
  - git: "https://github.com/Jeremy-Demlow/dbt-cortex-agent.git"
    revision: v0.0.8
```

PyPI version `0.0.8` and Git tag `v0.0.8` identify the same immutable release
across the CLI and dbt surfaces. Run `dbt deps`, then
`dbt-cortex-agent doctor --project-dir . --json`; `doctor` verifies that the CLI,
declared dbt dependency, and installed consumer dbt package versions align. A
full immutable Git SHA is accepted only when actual installed package metadata
under `dbt_packages/dbt_cortex_agent` reports the matching version; a source
checkout's root `dbt_project.yml` is not installation evidence. The supported
runtime is Python `>=3.10,<4`, dbt
`>=1.10,<2.0`, and `dbt-snowflake`; see [compatibility](docs/reference/compatibility.md)
and [installation](docs/getting-started/installation.md).

The CLI also requires the Snowflake CLI (`snow`) on `PATH`; `doctor` checks both
the `dbt` and `snow` executables. By default, `dbt-cortex-agent init` configures
an existing dbt project by appending missing dependency and safety-variable
entries. It does not create a dbt project. Use `agent scaffold` to preview and
create a generic Agent model; a Semantic View and evaluation are optional.

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

## Five-minute first success

From an existing consumer dbt project, preview the files for a generic Agent.
This first command writes nothing:

```bash
dbt-cortex-agent agent scaffold --project-dir . --agent orders_assistant --json
```

After reviewing the plan, create the local files explicitly:

```bash
dbt-cortex-agent agent scaffold --project-dir . --agent orders_assistant --apply --json
```

The remaining checks are non-mutating. They install dependencies, generate a
fresh manifest, validate the selected Agent, compile its complete specification,
and preview deployment without connecting to Snowflake:

```bash
dbt deps
dbt-cortex-agent doctor --project-dir . --target sandbox --json
dbt-cortex-agent manifest validate --project-dir . --target sandbox --agent orders_assistant --json
dbt compile --project-dir . --target sandbox --select orders_assistant
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant \
  --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

Only `agent scaffold --apply` changes local files. None of these commands mutate
Snowflake. `dbt compile` renders the full Agent body without invoking its
materialization, and `agent deploy` without `--apply` reports the resolved
physical identity, skills, and dbt selection. Follow the
[quickstart](docs/getting-started/quickstart.md) for the complete explanation.

For Cortex Code-guided adoption, use the project-local
[`dbt-cortex-agent-project` skill](.cortex/skills/dbt-cortex-agent-project/SKILL.md).
It discovers an existing dbt project, establishes objective/levers/data/proof,
and guides an existing semantic view, the fixed Orders starter, or an existing
Agent into dbt-owned metadata. It is script-free, shows manual 0.0.8 command
parity, and stops separately before local writes, Snowflake mutation/runtime,
paid evaluation, and baseline movement. The checked-in skill is not a claim of
catalog publication or live Snowflake verification.

## Controlled deploy

Deploy selected Agents and their declared skills through one package workflow:

```bash
dbt-cortex-agent agent deploy --project-dir . --target sandbox \
  --agent orders_assistant --connection sandbox --database ANALYTICS_DEV \
  --allow-target sandbox --allow-database ANALYTICS_DEV --apply
```

The model relation determines the physical Agent FQN. The model body is passed
directly to the materialization, which validates explicit orchestration, checks
staged skills, updates LIVE, commits immutable `VERSION$N`, and reconciles the
configured alias. The package preflights and uploads selected skills before it
invokes the dbt dependency closure. dbt remains the sole Agent DDL authority.
No Makefile or copied adopter Python script is required.

Repository wrappers can still provide reviewed defaults, fleet selection,
approval checks, or report retention. They must delegate to the same package
commands rather than reimplementing deployment, runtime, or evaluation. If a
behavior must work for every adopter, it belongs in this package.

A target-resolved manifest may contain Agents in multiple approved databases.
The package carries each selected Agent's complete `database.schema.object`
identity through skill and runtime operations and validates every Agent, stage,
eval table, evaluation stage, and result database against repeatable allowlists.

```text
one dbt target manifest
  +-- FINANCE.AGENTS.FINANCE_ANALYST
  +-- MARKETING.AGENTS.CAMPAIGN_ANALYST
  +-- AI_FOCUS.AGENTS.ENTERPRISE_ASSISTANT

selected resource FQN -> allowlist validation -> bounded operation
```

One package invocation consumes one dbt target and its fresh manifest. Parsing
and coordinating several dbt targets belongs to adopter CI, where each target
has a separately reviewed role, warehouse, and approval boundary.
Read [lifecycle](docs/guides/lifecycle.md) and [Snowflake setup](docs/getting-started/snowflake-setup.md)
before crossing this boundary.

## Supported interfaces

| Need | Shipped CLI | Public dbt macro |
|---|---|---|
| Diagnose a project | `doctor` | — |
| Scaffold an Agent | `agent scaffold` | — |
| Validate resolved metadata | `manifest validate` | — |
| Render the full Agent spec | — | `dbt compile --select <agent_model>` |
| Deploy/version an Agent | `agent deploy` | `dbt build --select <agent_model>` (advanced primitive) |
| Preview/invoke any Agent | `agent smoke` | — |
| Inspect/promote/rollback versions | `agent versions`, `agent promote`, `agent rollback` | delegated lifecycle macros |
| Retire an Agent | `agent drop` | delegated `cortex_agent__drop` macro |
| Plan/upload/smoke skills | `skill plan/upload/smoke` | deploy validates staged skills |
| Render/run optional evaluation | `eval run`, `eval verify` | `cortex_eval__execution_plan`, `cortex_eval__run` |
| Compare/gate/accept artifacts | `eval compare/gate/accept-baseline` | threshold macros only |

Use the direct CLI for the complete reusable lifecycle. It delegates all Agent
mutation to the installed dbt package while adding fresh-manifest resolution,
preflight checks, stable exits/JSON, connector clients, and durable evidence.
Direct `dbt compile` remains the normal specification preview. Direct `dbt
build` and lifecycle macros are lower-level interfaces for operators who
deliberately own their surrounding sequencing. Python provisions no stage and
contains no mutating Agent DDL.

## Explicit effect boundaries

Every effectful operation is preview-first. Cross one boundary at a time:

| Boundary | Example | Explicit approval |
|---|---|---|
| Local file write | `agent scaffold` | `--apply` |
| Snowflake mutation | `agent deploy`, `agent promote`, `agent rollback` | connection, complete allowlists, `--apply` |
| Runtime invocation | `agent smoke`, `skill smoke` | connection, complete allowlists, `--apply` |
| Paid evaluation | `eval verify`, `eval run` | connection, warehouse, complete allowlists, `--apply` |
| Baseline policy change | `eval accept-baseline` | reviewed candidate and `--apply` |
| Destructive retirement | `agent drop` | exact physical FQN confirmation, complete allowlists, `--apply` |

Snowflake Agent DDL is non-transactional. Applied commands record completed
durable phases and verify postconditions; they do not claim that a later failure
rolled back an earlier version commit or route change. Inspect returned state,
correct the underlying problem, and retry the same desired operation.

## Lifecycle and evaluation

The materialization validates and hashes the rendered spec plus staged skills,
skips unchanged managed versions independently of serving DEFAULT, commits an
immutable version only when content changes, and applies the requested alias.
Promotion, rollback, guarded retirement, grants, MCP attachment, and skill smoke
remain explicit operations.

Evaluation is optional and targets the same Agent selected by the model relation.
`eval run` is a client for that already deployed Agent, a materialized
eval table, and an evaluation stage; `--apply` incurs Cortex spend. It never
deploys or changes an Agent. It writes candidate JSON with plan identity,
ordered ground-truth refs, policy, and pre/post DEFAULT provenance for threshold
and accepted-baseline gates. See [evaluations](docs/guides/evaluations.md).

For a complete evaluation workflow, `eval verify` materializes and tests the
selected eval model, executes native evaluation, consumes the exact candidate,
and applies intrinsic thresholds or an established baseline. Preview is free;
`--apply` is paid. Baseline acceptance remains a separate explicit command.

## Documentation

Start with the [documentation index](docs/README.md). It provides the canonical
reading order for installation, first use, the complete developer lifecycle,
architecture, exact references, CI/CD, troubleshooting, and releasing.

## Limitations and policies

- Snowflake and dbt Core with `dbt-snowflake` are the release authority; DuckDB is unsupported and Fusion is advisory.
- `dbt build --select <agent_model>` deploys model Agents; `dbt compile` is the non-mutating preview.
- Property YAML may use `target`, `var`, and `env_var`, but cannot call package macros.
- Skills and MCP connectors are excluded from built-in native Agent Evaluation and require separate smoke/integration proof.
- Live mutation, runtime smoke, and evaluation spend are never default operations.
- This independent, maintainer-led package is not sponsored, endorsed, supported, or maintained by Snowflake Inc.

Apache License 2.0. See [LICENSE](LICENSE), [contributing](CONTRIBUTING.md),
[security](SECURITY.md), [support](SUPPORT.md), and [Code of Conduct](CODE_OF_CONDUCT.md).