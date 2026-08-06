# Upgrade from v0.2.0 to v0.3.0

Version 0.3.0 packages the dbt macros and Python CLI as one release with a stable
manifest-owned contract. Upgrade both install surfaces together.

## Replace dependencies

Pin the dbt package to `v0.3.0` and install the Python distribution at `0.3.0`:

```yaml
packages:
  - git: "https://github.com/Jeremy-Demlow/dbt-cortex-agent.git"
    revision: v0.3.0
```

After v0.3.0 is published to PyPI:

```bash
pipx install 'dbt-cortex-agent[runtime]==0.3.0'
# Managed environment equivalent:
python -m pip install --upgrade 'dbt-cortex-agent[runtime]==0.3.0'
dbt deps
```

Before publication, environments that can access the repository can install the
current source snapshot pinned to commit `7027d45613423e90a522a8e1ec283c6ce56f33bc` with
`pipx install 'dbt-cortex-agent[runtime] @ git+https://github.com/Jeremy-Demlow/dbt-cortex-agent.git@7027d45613423e90a522a8e1ec283c6ce56f33bc'`.
dbt remains a separate HTTPS Git dependency because `dbt deps` does not install
packages from PyPI. Public adopters need the repository and `v0.3.0` tag to be
published before that dependency resolves. PyPI `0.3.0` and Git tag `v0.3.0` are the same immutable
release; run `dbt-cortex-agent doctor --project-dir . --json` after `dbt deps` to
verify the CLI, declaration, and installed dbt package align.

Replace former `dbt-cortex-agent[invoke]` and `dbt-cortex-agent[eval]` installs
with `dbt-cortex-agent[runtime]==0.3.0`. Remove local lifecycle/eval scripts and
repository-specific Make wrappers; use the installed CLI commands.

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

Run consumer tests and review canonical/native-eval render differences. Any
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
the native-eval Agent, eval table, and stage prerequisites exist; gate it, review
policy/provenance, then accept it explicitly if approved.

## Deploy deliberately

Use an isolated sandbox, explicit `--connection` and `--database`, matching CLI
and dbt allowlists, and `--apply`. Keep production promotion and baseline moves
as separate approvals.

Internal helper macros are not stable API. See [macro reference](docs/reference/macros.md)
and [CLI reference](docs/reference/cli.md).