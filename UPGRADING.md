# Upgrade to v0.3.1

Version 0.3.1 is one release scope: the curated Orders starter, one physical
Agent with optional same-Agent evaluation, general Agent smoke, the guided
project-local Cortex Code skill, and immutable-SHA doctor validation. Upgrade
both install surfaces together.

## Replace dependencies

Pin the dbt package to `v0.3.1`. Version 0.3.1 is not published to PyPI yet, so
install the reviewed Python distribution from a clean local checkout:

```yaml
packages:
  - git: "https://github.com/Jeremy-Demlow/dbt-cortex-agent.git"
    revision: v0.3.1
```

```bash
pipx install '/absolute/path/to/dbt-cortex-agent[runtime]'
# Managed environment equivalent:
python -m pip install --upgrade '/absolute/path/to/dbt-cortex-agent[runtime]'
dbt deps
```

dbt remains a separate HTTPS Git dependency because `dbt deps` does not install
packages from PyPI. Public adopters need the repository and `v0.3.1` tag to be
published before that dependency resolves. Future PyPI `0.3.1` and Git tag `v0.3.1` will be the same immutable
release; run `dbt-cortex-agent doctor --project-dir . --json` after `dbt deps` to
verify the CLI, declaration, and installed dbt package align.

For immutable commit pins, doctor requires the installed consumer package at
`dbt_packages/dbt_cortex_agent/dbt_project.yml` to report version `0.3.1`.
The package source checkout's root `dbt_project.yml` is not accepted as proof
that the consumer ran `dbt deps`. Branch revisions and mismatched installed
metadata fail closed; semantic `v0.3.1` pins continue to match directly.

Replace former `dbt-cortex-agent[invoke]` and `dbt-cortex-agent[eval]` installs
with `dbt-cortex-agent[runtime]==0.3.1`. Remove local lifecycle/eval scripts and
repository-specific Make wrappers; use the installed CLI commands.

The repository also ships the script-free
[`dbt-cortex-agent-project`](.cortex/skills/dbt-cortex-agent-project/SKILL.md)
skill for Cortex Code-guided adoption. It uses the same stable CLI and metadata
contracts and stops independently before local writes, Snowflake operations,
paid evaluation, and baseline movement.

## Make safety policy explicit

Set `cortex_agent_deploy_target`, `cortex_agent_allowed_targets`, and a non-empty
`cortex_agent_allowed_databases`. Do not rely on inherited `dbt_focus`, sandbox,
database, schema, or repository defaults. Preview missing values with `init`
before applying file changes.

## Confirm metadata and layout

- Agents remain exposures at `config.meta.cortex_agent`.
- Eval suites remain table models at `config.meta.cortex_eval`.
- Tool semantic models resolve through dbt model names.
- Private/shared skill paths mirror their declared stage suffix.
- Eval questions have unique `ground_truth_ref` and input text.

## Prove parity without mutation

```bash
dbt-cortex-agent doctor --project-dir . --json
dbt-cortex-agent manifest validate --project-dir . --json
dbt-cortex-agent agent render --project-dir . --json
dbt-cortex-agent agent deploy --project-dir . --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

Run consumer tests and review the one full rendered specification. Any
rendered-spec change can mint a version when later applied.

## Migrate evaluation evidence

The v0.3.0 CLI uses dbt-rendered plan identity and candidate artifact schema v2.
Do not accept an old or incompatible baseline automatically. Known passing
pre-schema/schema-v1 accepted artifacts can be previewed with:

```bash
dbt-cortex-agent eval migrate-baseline legacy.json \
  --project-dir . --target sandbox \
  --agent orders_assistant --suite core \
  --baseline-dir target/dbt_cortex_agent/baselines --json
```

The current dbt plan supplies all identity and policy fields; legacy summary and
run provenance are retained. Add `--apply` only after review. Existing targets
also require `--force`; no overwrite is implicit. Unknown shapes or metric-set
mismatches fail closed. Alternatively, produce a new paid candidate only after
the normal Agent, eval table, and stage prerequisites exist; gate it, review
policy/provenance, then accept it explicitly if approved.

## Deploy deliberately

Use an isolated sandbox, explicit `--connection` and `--database`, matching CLI
and dbt allowlists, and `--apply`. Keep production promotion and baseline moves
as separate approvals.

Internal helper macros are not stable API. See [macro reference](docs/reference/macros.md)
and [CLI reference](docs/reference/cli.md).