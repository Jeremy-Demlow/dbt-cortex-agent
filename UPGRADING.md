# Upgrading dbt_cortex_agent

## Versioning policy

- **Major:** breaking metadata, public macro, rendered-spec, or lifecycle changes.
- **Minor:** backward-compatible fields, tools, macros, or capabilities.
- **Patch:** fixes and documentation that preserve the rendered contract.

Internal helper macros are not stable API. The supported surface is listed in
[`docs/reference/macros.md`](docs/reference/macros.md).

## Upgrade procedure

1. Pin the intended package release or local revision.
2. Run `dbt deps` from a clean dependency directory.
3. Run `dbt parse` and compile all Agent eval models.
4. Render both Agent projections and review the diff before mutation.
5. Run package and consumer contract tests.
6. Dry-run deployment in the allowed sandbox target.
7. Deploy and evaluate only after reviewing intentional spec changes.

Do not update accepted eval baselines merely because a package version changed.
Move a baseline only after a passing run and documented human acceptance decision.

## Rendered-spec changes

Any change to canonical or native-eval JSON can mint a new Agent version. Treat a
golden-spec difference as a deployment change even when metadata remains valid.
