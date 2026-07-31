# CI adoption

Use progressive gates.

## Package checks

1. `dbt deps`
2. `dbt parse`
3. compile Agent eval models
4. validate Agent/eval metadata
5. render canonical and native-eval specs
6. compare renders with reviewed snapshots
7. dry-run deployment

## Full framework checks

Optional copyable tooling adds:

- manifest discovery,
- eval dataset run/test,
- state-based Agent scoping,
- skill upload and smoke,
- spend-bearing live evaluation,
- accepted-baseline comparison.

Do not make a live evaluation an unlabeled default. Missing base state may widen
evaluation scope for correctness, so CI must make that cost behavior visible.

For skill changes, CI should call one upload-before-canonical-deploy orchestrator
for the affected exposure names, then smoke each selected Agent separately. Shared
library skill changes must select every declaring Agent.

See the containing repository workflow for a full reference implementation; copy
and parameterize it rather than assuming the dbt package installs it.

Copyable starting points:

- [`package-check.yml`](../../.github/workflows/package-check.yml) — active standalone
  dependency, parse,
  compile, validation, deterministic render, and deployment dry-run.

The containing framework repository also provides a full-framework template for
selected skill deployment/smoke and optional paid evaluation. It is deliberately
outside the package because it requires copied Python, Make, and evaluation tooling.

Both templates require consumer-specific roles, objects, package coordinates, and
secret setup. The full-framework template assumes the copyable Python/Make tooling
has been adopted alongside the package.
