# REQ-010: trusted PyPI publishing

## Summary

Publish verified Python distributions from a published GitHub release through PyPI trusted
publishing, without a long-lived API token.

## Business context

REQ-008 proves that the package can be built and inspected without credentials, but no protected
automation publishes the verified artifacts. A release operator needs one auditable path that
binds the Git tag, Python package version, dbt package version, changelog, built artifacts, GitHub
environment approval, and PyPI's OIDC trust relationship.

## Objective

A maintainer can publish one immutable, version-aligned Python and dbt release without creating,
storing, or exposing a PyPI API token.

## Acceptance criteria

1. `.github/workflows/release.yml` runs only for a published GitHub release or a manual build-only
   dispatch; it never runs for push or pull request events.
2. The build job has read-only repository permissions, checks out the selected tag, uses a
   supported Python version, runs the release preflight and full test suite, builds with pinned
   tooling, runs Twine metadata checks and wheel inventory checks, and uploads the distributions.
3. The publish job runs only for a published release whose tag starts with `v`, uses the dedicated
   `pypi` GitHub environment, receives only `contents: read` and `id-token: write`, downloads the
   verified build artifact, and invokes a version-pinned `pypa/gh-action-pypi-publish` action.
4. No workflow or documentation requires a PyPI username, password, API token, or repository
   secret for publication.
5. `scripts/release_preflight.py` fails closed unless the checkout is clean, the supplied tag is a
   semantic `v*` tag at `HEAD`, Python and dbt project versions equal the tag version, and the
   matching changelog heading contains a release date rather than `Unreleased`.
6. Automated tests cover successful `v0.3.0` preflight simulation and failures for dirty state,
   malformed or missing tags, version mismatch, and unreleased/missing changelog entries.
7. Maintainer documentation explains PyPI trusted-publisher configuration, the required GitHub
   `pypi` environment, release preparation, tag/release ordering, manual build-only validation,
   and post-publication verification.
8. YAML parsing, workflow contract tests, full tests, package build, Twine checks, wheel inventory,
   and a simulated clean `v0.3.0` preflight pass without creating a commit, tag, release, or
   publication.

## User stories

- As a release operator, I can publish from a protected GitHub release without managing a PyPI
  API token.
- As a package consumer, I can trust that the PyPI and dbt Git versions identify the same release.
- As a security reviewer, I can prove that OIDC permission is isolated to the protected publish
  job and cannot be reached from push, pull request, or manual runs.
- As a maintainer, I can run the exact release preflight and artifact checks before publication.

## Dependencies

- REQ-002 v0.3.0 identity and Python ownership.
- REQ-007 complete adopter documentation.
- REQ-008 standalone CI and release verification.
- REQ-009 simple maintainer-led project policy.

## Out of scope

- Creating a commit, Git tag, GitHub release, or PyPI project.
- Configuring the GitHub environment or PyPI trusted publisher on behalf of the owner.
- Publishing an artifact, changing repository visibility, or mutating Snowflake.
- Changing package, dbt, Agent, evaluation, or runtime behavior.

## Notes

- Objective lever: bind publication authority to GitHub's release event, a protected environment,
  and PyPI's short-lived OIDC exchange after deterministic artifact verification.
- Data proof: package metadata and dbt metadata already identify `0.3.0`; the changelog intentionally
  remains `Unreleased`, so the real checkout is not release-ready until the maintainer dates it.
- Assembly line: prepare version/changelog -> create immutable tag -> publish GitHub release ->
  preflight/test/build/check/upload -> protected OIDC publish.
- Reversible local choice: `workflow_dispatch` accepts an existing tag and exercises build-only;
  manual runs cannot publish.
- Verifier: required because this slice changes release execution and package publication behavior.
- Critic: the initial contract conflicted with REQ-008's single-package-workflow assertion and the
  changelog check accepted date-shaped invalid calendar values. The workflow contract now permits
  exactly the package gate plus the release workflow, and preflight uses ISO calendar validation.
  Focused workflow, documentation, and preflight tests have no blocking findings.
- Verification on 2026-08-05: both root workflow files parsed; all 202 Python tests passed; the
  clean tagged `v0.3.0` fixture passed both function and CLI preflight paths; pinned `build==1.3.0`
  produced the sdist and wheel; pinned `twine==6.2.0` checks and exact wheel inventory passed;
  `git diff --check` passed; generated build, distribution, and egg-info residue was removed. No
  commit, tag, release, publication, visibility change, credential configuration, or Snowflake
  operation occurred.
