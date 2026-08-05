# REQ-009: simple maintainer-led project policy

## Summary

Remove invented publication governance gates and describe the repository as a simple
maintainer-led Apache-2.0 project.

## Business context

The repository currently claims that merge, release, security, and publication are blocked by a
vacant second maintainer, special employer-rights evidence, and legal review. Those gates are not
part of the desired project policy and make ordinary contribution and release activity appear
prohibited.

## Objective

Contributors and maintainers can use the project without encountering invented publication
blocks while retaining clear licensing, security-reporting, support, and technical verification
expectations.

## Acceptance criteria

1. `GOVERNANCE.md` and `MAINTAINERS.md` are removed, and no remaining local link references them.
2. README, CONTRIBUTING, the pull request template, CODEOWNERS, Code of Conduct, SUPPORT,
   THIRD_PARTY_LICENSES, and CITATION use simple maintainer-led project wording with no
   two-maintainer, vacant-role, employer-approval, legal-review, or publication-block gate.
3. Contributions retain only minimal Apache-2.0 authorization and attribution language; no
   special employer approval claim remains.
4. Private security reporting and best-effort community support remain documented.
5. Requirements, user stories, test cases, and automated policy/project-health contracts reject
   reintroduction of the removed gates and verify the retained policy surfaces.
6. Repository visibility and package publication automation are unchanged.
7. Full tests, focused docs/policy tests, tracked-file secret scanning, and package build pass.

## User stories

- As a contributor, I can understand the license and submit work without invented employer or
  publication approvals.
- As a maintainer, I can lead project decisions without a fabricated vacant-role block.
- As a security reporter, I retain a private reporting route.
- As a package consumer, I can rely on explicit best-effort support and technical release checks.

## Dependencies

- REQ-007 complete adopter documentation.
- REQ-008 standalone CI and release verification.

## Out of scope

- Repository visibility changes.
- PyPI publishing or release workflow changes.
- Changes to Agent, evaluation, dbt, or Snowflake runtime behavior.

## Notes

- Objective lever: remove policy text and contracts that turn review practices into invented
  publication prohibitions while preserving technical verification and security boundaries.
- Data proof: repository-wide policy search and existing docs/CI tests identify every affected
  surface and provide deterministic local verification.
- Assembly line: requirement -> policy edits -> contract tests -> critic review -> full local
  verification.
- Verifier: substituted by full docs/policy tests, full Python tests, tracked-file secret scan,
  package build, and final repository-wide phrase/link checks because this slice changes policy
  and configuration text only, not SQL, macros, models, eval semantics, or deploy behavior.
- Critic: a malformed duplicated dependency-review clause and an overly literal security-policy
  assertion were corrected. Verification commands were also scoped explicitly to this repository
  after the initial shell working directory caused unrelated test discovery and path resolution.
  No blocking finding remains against the acceptance criteria.
- Verification on 2026-08-04: 65 focused documentation/policy/CI contract tests and all 182
  Python tests passed; the tracked non-lock file secret scan reported zero findings; `uv build`
  produced the v0.3.0 sdist and wheel; final phrase/link checks and `git diff --check` passed.
  Repository visibility, publishing automation, git history, Snowflake state, and package runtime
  behavior were not changed.
