# REQ-008: standalone CI and release verification

## Summary

Provide one active root GitHub Actions workflow that verifies the dbt package and
Python distribution without Snowflake credentials, live operations, or evaluation spend.

## Business context

The recovered package workflow depends on private-key secrets and a live Snowflake
profile, so pull requests cannot independently prove compatibility, deterministic
rendering, package integrity, or installer behavior. Release evidence must be available
before any separately approved sandbox deployment or paid evaluation.

## Objective

A maintainer can trust every pull request, push, and manual package-CI run to reject an
incompatible or unsafe release artifact using only deterministic local evidence.

## Acceptance criteria

1. `.github/workflows/package-check.yml` is the only active package workflow and runs on
   pull request, push, and `workflow_dispatch` with read-only repository permissions.
2. CI requires no repository secrets, Snowflake credentials, live connection, `--apply`,
   runtime invocation, baseline movement, or paid evaluation.
3. Python tests run on every declared supported interpreter: 3.10, 3.11, 3.12, and 3.13.
4. dbt compatibility runs against lower-bound `dbt-core~=1.10.0` with
   `dbt-snowflake==1.10.3` and authority `dbt-core~=1.11.0` with
   `dbt-snowflake==1.11.4`, consistent with `require-dbt-version: >=1.10,<2.0`.
5. CI runs policy, documentation, project-health, full Python, byte-compilation, dbt
   dependency/parse, deterministic macro, canonical/native-eval render, execution-plan,
   and dry-run lifecycle checks using local fixtures and fakes.
6. CI verifies version alignment across Python, dbt, citation, lock, and current docs;
   pyproject/dbt compatibility; the expected wheel inventory; and absence of generated
   residue or tracked secret material.
7. CI builds sdist and wheel, runs Twine metadata checks, installs the wheel into a clean
   environment outside the checkout, and exercises CLI help, version, and fixture preview.
8. CI emits dependency-license inventory and a CycloneDX SBOM using pinned tools, while
   keeping generated evidence outside the checkout and uploading it as non-secret artifacts.
9. Workflow contract tests prevent nested/inactive workflow confusion and fail if package
   CI gains secret interpolation, Snowflake credential variables, mutation, paid evaluation,
   or unapproved live jobs.
10. Local verification runs the equivalent checks available on the maintainer platform,
    cleans generated residue, and records any unavailable matrix proof honestly.

## User stories

- As a maintainer, I receive compatibility evidence for every supported Python and dbt line.
- As a security reviewer, I can prove default CI cannot mutate Snowflake or spend credits.
- As a release operator, I can install the exact wheel outside the source checkout and use
  its CLI before publishing it.
- As a consumer, I can inspect license and SBOM evidence for the verified dependency set.

## Dependencies

- REQ-002 v0.3.0 identity and Python ownership.
- REQ-004 lifecycle and safety hardening.
- REQ-005 dbt-rendered evaluation execution plan.
- REQ-006 stable domain-oriented CLI.
- REQ-007 complete adopter documentation.

## Out of scope

- Snowflake authentication, secrets, users, roles, network policies, or live objects.
- Live skill smoke, Agent deployment, baseline acceptance, or paid evaluation.
- Commit, push, workflow execution, release publication, or promotion.

## Notes

- Objective lever: make deterministic package and consumer evidence mandatory before any
  separately approved live stage.
- Data proof: package metadata declares Python `>=3.10,<4`; dbt 1.9.10 with adapter
  1.9.4 fails the integration fixture's generic-test `arguments` contract, while dbt
  1.10.22 with adapter 1.10.3 passes offline deps/parse and 73 deterministic tests;
  adapter 1.11.4 remains the project authority selected by the task.
- Assembly line: policy/contracts -> Python matrix -> dbt matrix -> build/metadata -> clean
  wheel install/preview -> license/SBOM artifacts -> residue check.
- Reversible local choice: use one root workflow with independent jobs and no live-job
  placeholder; approved live checks can be added later as a separate protected workflow.
- Compile constraint: `dbt compile --no-introspect` still opens the Snowflake adapter and
  fails against the intentionally nonexistent offline key, so credential-free CI uses dbt
  parse plus macro/source determinism and Python byte-compilation. Credentialed dbt compile
  remains a separately approved integration proof and is not represented as passing here.
- Verifier: required because this slice changes CI execution, package verification, and dbt
  compatibility behavior; no live proof may substitute for the offline verifier.
- Critic: blocking findings were corrected for a secret-scan contract false positive,
  repository-clean timing before build cleanup, SBOM omission of the built wheel, Python
  3.10 test incompatibility, and an unsupported dbt 1.9 floor. No blocking finding remains.
- External-cwd hardening (2026-08-10): the tracked-file scan now resolves every relative
  path from `GITHUB_WORKSPACE`, so copying the workflow command into another checkout cannot
  scan same-named files from the caller repository. This preserves all real package findings
  and adds no detector, baseline, file, or path exclusion.
- Verification on 2026-08-04: 179 tests passed on Python 3.10, 3.11, and 3.13;
  Python 3.12 was unavailable locally and remains CI-matrix proof. dbt Core 1.10.22 with
  dbt-snowflake 1.10.3 and dbt Core 1.11.11 with dbt-snowflake 1.11.4 completed offline
  deps/parse; the lower line passed 73 focused deterministic tests. `git diff --check`,
  Python byte-compilation, pinned secret scanning, sdist/wheel build, Twine checks, exact
  wheel inventory, clean external install, CLI help/version/non-writing preview, dependency
  license JSON, CycloneDX SBOM, and generated-residue cleanup passed. `dbt compile
  --no-introspect` was attempted and correctly recorded as blocked by adapter authentication.
  No commit, push, workflow run, secret configuration, connection, live operation, baseline
  movement, or paid evaluation occurred.
