# REQ-028: Executable Developer and CI/CD Guide

**Status:** In progress; historical `0.0.6` evidence is not current qualification.

## Summary

Ship executable source material for a developer-facing article that teaches the complete package workflow from creation through protected CI/CD and retirement.

## Acceptance Criteria

1. The guide explains Python/dbt ownership and pins matching PyPI `0.0.6` and dbt Git `v0.0.6` coordinates.
2. It demonstrates generic Agent scaffolding first, with Semantic View, Search, skills, MCP, evaluation, and experimental mappings as optional additions.
3. It covers doctor, manifest validation, parse, compile, deploy preview/apply, compact smoke, and controlled failure recovery.
4. It covers evaluation authoring, preview, paid verify, candidate evidence, quality gates, and separate baseline acceptance.
5. It covers version inventory, direct-version smoke, promotion, rollback, roll-forward, no-change reconciliation, and guarded retirement.
6. It provides PR, protected-main deployment, concurrency, approvals, exact-wheel qualification, and release-publishing examples without copied package mechanics.
7. It documents authentication, least privilege, allowlists, runtime/evaluation cost boundaries, non-transactional phases, and retained evidence.
8. Every package command snippet is parsed or syntax-tested against the shipped CLI; core journeys run in an installed-consumer fixture.
9. Package and adopter Cortex skills, README, CLI reference, testing guide, and article source contain no stale release or contradictory ownership claims.
10. A machine-readable evidence map links article claims to requirement criteria and offline/live proof artifacts without secrets or customer data.

## Evidence

Offline qualification on 2026-08-28 verifies documented commands, CI gates,
release preflight behavior, wheel inventory, Twine metadata, and coherent sdist
requirement/test evidence.

`TC-028-01` through `TC-028-10` in `tests/test_cases.md`.

## 0.0.9 Candidate Preparation (2026-09-18)

Objective: reviewers can qualify the current hardening as a distinct 0.0.9
candidate without overwriting 0.0.8 history or mistaking local checks for release.

Acceptance criteria for this version-only slice:

- Align Python/dbt/runtime/citation/lock identity, current install examples,
  CI version assertions, and normative fixtures at 0.0.9.
- Date the candidate changelog 2026-09-18 and label qualification/publication
  pending. Preserve dated historical changelog and archived 0.0.8 evidence.
- Restore the historical narrow requirements ignore exceptions and add only
  REQ-032; leave generated/account-specific evidence ignored.
- Run offline tests, Ruff lint/format checks and configured mypy with existing
  dependencies; report failures and unrun gates without changing hardening code.

User story: a release reviewer can distinguish candidate identity, local proof,
historical evidence, and the remaining exact-wheel/live publication gates.
Dependencies: existing release identity tests, documentation contracts and REQ-032.
Levers/data: version metadata, existing docs/tests and read-only Git history.
Assembly line: inspect -> align candidate -> offline checks -> qualification handoff.
Out of scope: installs, network, Snowflake, Git mutation, commits, branches, tags,
push, publication, paid evaluation, baseline movement and runtime/macro changes.

Decision: retain historical 0.0.8 requirements evidence unchanged. The release
preflight test module creates temporary Git commits/tags, so it is excluded under
the explicit no-Git-mutation constraint and must remain an unrun gate.
Verifier: substituted by version/docs/CI contracts and offline quality checks
because this slice changes version/config/documentation only, not runtime logic.
Maker, critic, fix and verifier are sequential local passes, not independent agents.

Verification on 2026-09-18 used the existing environment with
`PATH=/Library/Developer/CommandLineTools/usr/bin:$PATH UV_OFFLINE=1 uv --directory
<repo> run --no-sync` (and disabled dbt anonymous usage statistics for pytest):

- `pytest -q --ignore=tests/test_release_preflight.py --cov=dbt_cortex_agent
  --cov-branch --cov-report=term-missing --cov-fail-under=75`: **802 passed**,
  **86.70%** combined statement/branch coverage, above the unchanged 75% gate.
- `ruff check src/dbt_cortex_agent tests scripts`: passed.
- `ruff format --check src/dbt_cortex_agent tests scripts`: 71 files already formatted.
- `mypy`: passed for the configured 12 source files.
- `dbt-cortex-agent --version`: `0.0.9`.
- Read-only `git diff --check` passed; `.gitignore` differs from HEAD only by
  the REQ-032 exception. Read-only ignore checks keep generated requirements
  evidence and `evidence/` ignored; REQ-032 is visible untracked, not staged.
- The 12 release-preflight cases were collected only, not executed. Their
  temporary-repository commits/tags conflict with the no-Git-mutation constraint.

Critique retained historical changelog/qualification sections, labeled current
compatibility and install examples as candidate contracts, and fixed the existing
doctor matching-version branch fixture to actually use the candidate version.
No blocking finding remains for version preparation. The requested unrestricted
full-suite run is not claimed: release-preflight execution, mutation gate,
distribution build/Twine/inventory, clean-wheel supported-dbt matrix, protected
live proof and publication remain separate pending gates. No runtime/macro logic,
baseline policy, remote state, Git history or archived distributions were changed.

## Task 6 Evidence Hardening (2026-09-17)

### Objective And Business Context

Reviewers can distinguish demonstrated behavior from source checks, historical
live reports, and missing proof. A comment containing a test-case ID must never
qualify an acceptance criterion. This is task 6 only; preserve task 1-5 changes.

### Slice Acceptance Criteria

- Replace token scanning with an explicit JSON claim/criterion/proof map covering
  every numbered acceptance criterion in REQ-021 through REQ-032 exactly once.
- Link offline proofs to concrete collected pytest functions or parameter nodes,
  label behavioral versus structural evidence, and record uncovered gaps rather
  than assigning unrelated tests. Collection is linkage, not a passing run.
- Distinguish historical live reports from pending live qualification. No new
  live evidence, installed-wheel execution, or release qualification is invented.
- Reject nonexistent IDs and comment-only markers. Validate the map schema,
  completeness, fixture schemas, local reference containment, and proof kinds.
- Correct Complete statuses that overclaim current/new proof and retain historical
  statements as provenance. Run focused offline tests and report exact gaps.

### User Stories, Dependencies, And Scope

As a reviewer, I can follow an article claim to its criterion and bounded proof,
and see what remains unproven. Dependencies are existing requirements, test cases,
pytest collection, compatibility/protocol fixtures, and task 1-5 behavior tests.
No runtime/macro/model changes, external services, installs, network, Snowflake,
paid evaluation, baseline changes, commits, branches, or broad cleanup are in scope.

### Notes And Verification

Use `tests/requirement_evidence.json`, with repository-relative references only.
Each criterion has a bounded claim, explicit proof references and explicit gaps.
Historical requirement prose is a report pointer, not a retained live artifact.
Fixture contracts describe synthetic local compatibility and SSE payload shapes;
they do not claim to validate every production Snowflake payload. Use the current
pytest session's collector APIs for linked modules, never a recursive pytest run.
Parameterized function selectors resolve to their concrete collected cases.

Maker, critic, fix, and verifier are sequential local passes, not independent
subagents. Verifier is offline pytest; actual dbt parse/compile and installed/live
journeys remain pending. This slice changes proof contracts, not deployment logic.
Results pending implementation and verification.

## Task 7 Local Product Contract (2026-09-18)

### Objective And Business Context

Adopters can follow the shipped interfaces without relying on nonexistent grants,
implicit role switching, or offline promises that hide network/local-write effects.
Release operators can distinguish successful proof from failed or unattempted proof
and cleanup while retaining both database observations. Preserve tasks 1-6.

### Slice Acceptance Criteria

- Remove instructions to invoke the absent grant macro; keep grants external.
- Correct role ownership, explicit skill metadata, and offline versus no-Snowflake-
  mutation versus local-write boundaries. Use one sandbox target throughout the
  canonical adopter sequence and document resolved-schema prerequisites/outcomes.
- Retain both Agents' observations, reconciliation snapshots, proof status, and
  cleanup status in attestation schema version 1 with additive fields. Failed
  proof/cleanup and cleanup-only without proof must never report completed proof.
- Separate cleanup-only updates preserve prior proof identity and outcomes; a
  different target/database/wheel must not be attached to existing evidence.
- Exercise failures and default-schema consumer identity locally, strengthen the
  existing installed-wheel harness where feasible, and retain the task 6 evidence
  map schema, criterion inventory, bounded proof classifications, and explicit gaps.
- Add UNRELEASED notes and protected-live setup/checklist guidance. Keep 0.0.8,
  its tag, and publication untouched; do not mark broader requirements complete.

### User Stories, Dependencies, And Scope

As an adopter, I can tell what each preview writes or contacts. As a release
reviewer, cleanup success cannot hide failed proof or erase database B. Depends
on the current manifest, macro harness, installed-wheel verifier, and task 6 map.
Levers are documentation, local verifier evidence, and behavioral tests. Assembly
line: inspect contracts -> correct guidance/evidence -> inject local failures ->
run offline quality gates -> report remaining release qualification.

Out of scope: new grant functionality, network/install/Snowflake operations,
paid evaluations, baseline changes, version bumps, tags, commits, branches,
publication, and independent subagents (not available in this session).

### Notes And Verification

Maker, critic, fix, and verifier are sequential local passes. No verifier
substitution: behavioral tests and the offline quality gates are required.
Additive attestation statuses distinguish proof from cleanup. Error evidence
retains exception types, not subprocess output or connection/credential details.
Existing proof observations describe pre-retirement state, not surviving Agents.
Default dbt schema naming is checked against locally installed dbt where available;
mocked materialization effects are not a real deployment or clean-wheel install.

Task 7 local verification (2026-09-18):

- Final full suite: `705 passed in 28.03s`; combined statement/branch coverage
  `86.21%` against the existing `75%` gate, Python 3.13.5. This is not branch-only
  coverage. The earlier focused run passed 97 tests in 5.27s before final additions.
- Global `ruff format --check src/dbt_cortex_agent tests scripts`: 71 files
  formatted; `ruff check` passed. Requested global formatting also normalized
  existing task 1-6 Python changes without changing their behavior.
- `mypy`: no issues in 12 source files. Mutation gate: all 6 mutants killed.
- Real credential-free temporary-consumer parse used already-installed dbt Core
  1.11.11 / dbt-snowflake 1.11.4 with telemetry disabled and no `dbt deps` or
  package installation. It resolved `ANALYTICS_AGENTS`; the Jinja harness then
  verified simulated deploy/comment/profile effects against that actual manifest.
- No-isolation sdist and wheel build passed using existing base setuptools 80.8.0
  via `PYTHONPATH`; the project venv alone lacked that backend. Twine checked both
  distributions successfully; wheel inventory passed. These local artifacts keep
  version 0.0.8 and are not a replacement release or clean-install qualification.
- `git diff --check` passed. Version files, lock, citation, and release/live
  workflow files remain unchanged. No installs, network, Snowflake, paid eval,
  baseline movement, branch, tag, commit, push, or publication was performed.
- Local critique/fix covered partial observation retention, setup/proof/cleanup
  failures, unchanged failed-proof status after cleanup retry, successful separate
  cleanup retention, matching identity, default schema behavior, and remaining
  role/grant/offline/scaffold documentation contradictions. No blocking finding
  remains against this local slice; independent subagent review was unavailable.

Exact-install matrices on both supported dbt lines, approved credentialed compile,
and protected exact-wheel live proof remain release blockers. The live setup
checklist is documentation, not evidence the environments or grants exist. Paid
Agent Evaluation is a separate approved qualification (`paid_evaluation: false`
must remain explicit). Broader REQ statuses and evidence-map gaps remain open.

## Final Review Isolation And Offline Verification (2026-09-18)

Objective: protected proof uses the pinned dbt installed in its isolated venv,
not an unrelated executable inherited from the caller. Levers: explicit child
environment binding shared by proof, lifecycle, retirement, and cleanup. Data:
local subprocess/environment fakes with conflicting inherited executables.
Assembly: construct isolated environment -> run proof -> retain attestation ->
reuse the same environment for cleanup.

Acceptance criteria:

- `DBT_EXECUTABLE` is always `<artifact_dir>/venv/bin/dbt`, matching the direct
  dbt command, regardless of inherited overrides or PATH discovery. All proof
  and cleanup paths use this binding without mutating the parent environment.
- Preview stays non-executing; cleanup-only remains usable without a venv because
  its bounded Snow CLI cleanup does not invoke dbt. Local fakes must not rely on
  a production fallback to a host dbt binary.
- REQ-030's HTTPError closure supplement has behavioral proof; the trivial
  `dbt_runner.py` kwargs typing correction passes explicit module checking
  without new ignores or behavior changes.
- Full offline pytest with combined statement/branch coverage, global Ruff
  format/check, configured mypy, explicit runner mypy, and the existing mutation
  gate run in the existing environment. Attempt a no-isolation build only with
  an already available backend. Record failures and qualification gaps honestly.

Dependencies: REQ-030/031 resource management and existing task 7 verifier tests.
Out of scope: live proof, installs/network, paid evaluation, commits, version
bumps, publication, and new lifecycle policy. Existing edits are preserved.
Verifier: mandatory sequential local maker/critic/fix/verifier; independent
subagents are unavailable.

Final-review results (2026-09-18):

- All Python checks used `PATH="/Library/Developer/CommandLineTools/usr/bin:$PATH" UV_OFFLINE=1 uv --directory /Users/jdemlow/00_Code/github/dbt-cortex-agent run --no-sync` with the existing Python 3.13.5 environment. No dependency installation, network, live Snowflake, commit, branch, version bump, or publication was performed.
- Full offline suite: **813 passed in 36.64s** with `pytest -q --cov=dbt_cortex_agent --cov-branch --cov-report=term-missing --cov-fail-under=75`. Combined statement/branch coverage **86.70%**, above the unchanged 75% gate; `invoke.py` reports 92%. This is not branch-only coverage or live compatibility proof.
- Final focused warnings-as-errors run: **132 passed in 0.62s** across invocation, live-verifier, execution-context, and fresh-manifest tests. Twenty added cases cover real stdlib HTTPError with synthetic bodies and the isolated proof environment, including a real subprocess attempt of an absent fake-venv dbt binary.
- Global `ruff format --check .`: **123 files already formatted**; `ruff check .`: passed. Formatting normalized three files: two changed test files and pre-existing formatting in `tests/test_deployment.py`; no existing test behavior was removed.
- Configured `mypy`: passed for 12 source files. Explicit `mypy src/dbt_cortex_agent/dbt_runner.py`: passed after reproducing the original kwargs assignment error and adding only a `dict[str, object]` annotation, with no new ignores.
- Existing mutation gate: **all 6 safety-critical mutants killed**. This bounded existing gate does not constitute mutation coverage of the two new fixes.
- Initial `python -m build --no-isolation` failed because the project venv lacks `setuptools.build_meta`. Repeating with command-local `PYTHONPATH=/Users/jdemlow/miniconda3/lib/python3.13/site-packages` used already-installed setuptools **80.8.0** and built the 0.0.8 sdist and wheel successfully. Existing base Twine checked both distributions; wheel inventory passed. These are local check artifacts, not a new release or clean-install qualification.
- Critique confirmed LIFO body/cursor/connection cleanup, preservation of the identical HTTP primary and secondary errors, no parsing of rejected HTTP bodies, parent-environment preservation, and shared executable binding through lifecycle/retirement/cleanup. Fake setup with no dbt fails proof and retains failed attestation; cleanup-only remains independent of dbt availability. No blocking findings remain for this narrow offline slice.

The full suite includes the existing credential-free default-schema consumer
parse against locally available dbt, followed by simulated materialization; it
does not install the newly built wheel. The project test venv has no real
Snowflake connector. Actual socket cleanup, approved credentialed compile,
clean exact-install matrices, protected live proof, and paid evaluation remain
unverified. No hard deadline or remote cancellation guarantee is added. Broader
requirement statuses and evidence-map gaps remain open.