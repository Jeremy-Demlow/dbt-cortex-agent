# CI

## Proof layers

Package CI uses separate trust boundaries:

```text
package-check.yml                 live-integration.yml              release.yml
credential-free                  protected snowflake-live-ci       exact tag/wheel
every PR and push                manual or scheduled               published release
unit/dbt/wheel contracts         multi-database mutation/smoke     live gate -> PyPI
```

`package-check.yml` never receives Snowflake credentials and never mutates or
incurs Agent Evaluation spend. `live-integration.yml` builds one wheel, installs
that exact artifact in an isolated environment, and uses the package-owned
integration consumer to prove same-named Agents in separate databases, immutable
versions/aliases, runtime smoke, schema-v2 eval-plan preview, and no-change
reconciliation. The default live proof does not start paid evaluation.

PyPI publication requires the protected live proof of the exact wheel built
from the release tag. The GitHub release event starts that qualification, so
publishing the GitHub release itself is not gated by this workflow. Manual
release workflow dispatch remains build-only.

Separate free/local proof, controlled sandbox mutation, and paid evaluation into
distinct jobs. Never make `--apply` or evaluation spend an unlabeled PR default.

## Pull request: non-spend

Run without live mutation or paid evaluation:

1. install matching dbt and Python 0.0.9 candidate artifacts (published pins only after release);
2. `dbt deps` and `dbt parse`;
3. run package/consumer tests and compile where credentials permit;
4. `dbt-cortex-agent doctor --json`;
5. `manifest validate` and `dbt compile --select <agent_model>`;
6. `skill plan` and `skill upload` without `--apply`;
7. `eval run` without `--apply` to validate the dbt-rendered plan;
8. compare deterministic renders and local gate artifacts with reviewed evidence.

The repository's active root [`package-check.yml`](../../.github/workflows/package-check.yml)
is the credential-free package release gate. It runs Python and dbt compatibility
matrices, deterministic fixture previews, distribution checks, clean-wheel smoke,
secret/residue guards, license inventory, and SBOM generation. It deliberately contains
no Snowflake secrets or live jobs. Consumer CI must supply its own package coordinates,
profiles, objects, roles, and secrets for separately approved live checks.

The separate [`release.yml`](../../.github/workflows/release.yml) workflow publishes only after a
GitHub release is published from a matching `v*` tag. Manual dispatch is build-only. Publication
uses the protected `pypi` environment and PyPI trusted publishing, so no API token is stored. See
[releasing](releasing.md) for owner setup and the release checklist.

`dbt compile`, including `--no-introspect`, opens the Snowflake adapter for this semantic
view fixture. The credential-free gate therefore uses `dbt parse`, deterministic macro
contracts, and Python byte-compilation; run `dbt compile` only in a separately approved,
credentialed integration job.

## Sandbox deploy: mutation

Use a protected job/environment and an isolated database. Require operator
approval, an explicit connection/database, repeatable CLI allowlists, matching
dbt vars, and explicit approval. Upload selected skills before `dbt build`;
build only selected Agents. Run live skill smoke afterward as a separate
runtime check.

Normal production Agents and semantic views must not be mutated by a sandbox
gate. Promotion beyond sandbox is a separate approved lifecycle operation.

## Paid evaluation: opt in

Run only after the sandbox job has separately:

- deployed the normal Agent selected by the full-body model,
- materialized and tested the eval table,
- provisioned/accessed `EVAL_CONFIG_STAGE`,
- selected an evaluation warehouse and cost controls.

Then invoke `eval run --apply`, gate the candidate, and retain artifacts. Baseline
acceptance is a separate reviewed mutation. Missing selection/base-state evidence
must not silently skip required suites; widening scope can increase spend, so make
the selected Agents/suites visible before approval.