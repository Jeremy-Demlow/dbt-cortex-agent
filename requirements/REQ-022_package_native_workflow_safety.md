# REQ-022: Package-Native Workflow Safety and Proof

**Status:** In progress; tasks 2/4 locally verified, historical `0.0.6` live evidence does not qualify new changes. See `tests/requirement_evidence.json` gaps.

## Summary

Harden `agent deploy` and `eval verify` so reusable execution lives in the package, all policy is checked before effects, and partial durable work is reported honestly.

## Acceptance Criteria

1. Deploy authorizes the selected target and every Agent, stage, and dependency database before upload or dbt execution.
2. Preview resolves plans without credentials, remote calls, local evidence writes, mutation, runtime invocation, or paid evaluation.
3. Apply uses one explicit connection context consistently across dbt, Snow CLI, connector, role, database, schema, and warehouse operations.
4. Authentication modes are either proven end to end for both package and dbt clients or rejected before execution with an actionable diagnostic.
5. Deploy reports each durable phase, including successful uploads or version commits preceding a later failure.
6. Evaluation completes all resource and policy validation before eval-model build or paid work.
7. Numeric thresholds, tolerances, scores, counts, and retry settings reject NaN, infinity, malformed values, and incomplete cardinality.
8. Evaluation infrastructure is pre-provisioned or explicitly managed outside the paid run; evaluation does not opportunistically create shared stages.
9. Multi-suite verification preserves every completed suite result and reports aggregate quality separately from infrastructure failure.
10. Candidate and diagnostic identities are collision-safe, contained, and never overwrite prior evidence implicitly.
11. Protected exact-wheel proof exercises the same public deploy and verify commands customers use.
12. Adopter scripts retain only fleet selection, environment policy, approvals, and reporting; they do not duplicate package mechanics.

## Partial-State Contract

Snowflake Agent DDL and uploads are durable phase by phase. Output records what completed and what failed; it never claims transaction rollback.

## Evidence

Offline qualification on 2026-08-28 covers policy-before-effect behavior,
authentication rejection, durable dbt phase markers, partial failures, numeric
validation, multi-suite evidence, and artifact collision safety. The protected
exact-wheel proof completed with wheel SHA256
`f926445177e3c2a93a7cc7089e909a7c6c310d9761a9650e5a1cf3fedcfbe4eb`.

`TC-022-01` through `TC-022-12` in `tests/test_cases.md`.

## Task 2 Correctness Supplement (2026-09-17)

Status: locally verified, no live qualification. Historical 0.0.6 evidence above
does not qualify this change. The named package-correctness-product-hardening
plan was not found in the checkout; this slice follows the user's explicit task
2 instructions. Task 1 edits are preserved and tasks 3 onward are out of scope.

Objective: incomplete, ambiguous, failed, or version-indeterminate evaluation
evidence cannot authorize a green gate or become an accepted baseline.

Levers/data/assembly line: validate the signed metric policy before effects;
join native rows to the validated source refs; validate observations before
aggregation; enforce eligibility through compare, gate, acceptance, and verify.
Existing `LifecycleCursor`, `PartialLifecycleCursor`, and `_rows` fixtures in
`tests/test_eval.py` contain one aggregate metric observation per input/metric,
with record/input IDs reused across metrics. They do not prove that RECORD_ID
is a question identifier in every native deployment. Source INPUT_QUERY is
already required to be unique and maps to a unique declared ground-truth ref.

Slice acceptance criteria (extend AC 6, 7, and 9):

- Compare, gate, verify (with/without baseline), and acceptance reject candidates
  unless status is completed and passed is exactly true; drift remains failed.
- Each declared source ref has exactly one finite score per applicable metric.
  Reject duplicate ref/metric observations even when record IDs differ; do not
  reject legitimate different metrics merely because native IDs differ.
- TOOL_METRICS on rows whose source test_type is not in_scope are excluded from
  scoring and completeness; absent/null/nonfinite excluded scores are allowed.
  Duplicates, unknown refs/metrics, and inconsistent test types still fail closed.
  Non-tool metrics remain required on boundary rows. An entirely excluded tool
  metric cannot satisfy an explicit threshold or regression policy.
- Reject threshold/tolerance keys absent from the declared contract before any
  build/connector/paid execution. Artifact counts/averages must be finite and
  agree with candidate row evidence; baselines retain the existing compact shape.
- Behavioral regression tests exercise real comparison/gate/verify functions and
  mocked native fetch/run boundaries, not source-string assertions.

User story: as a release operator, partial favorable scores cannot conceal a
failed evaluation or silently authorize baseline advancement.

Dependencies: REQ-005 plan/provenance, existing dataset annotation, and REQ-022
policy-before-effects. No new Agent architecture, SQL/macro behavior, retries,
baseline policy widening, release claims, or live execution are in scope.

Maker/critic/fix/verifier passes were local passes by the same agent; no independent
subagent tool is available. Critique checked positive boundary cases as well as
failures, native IDs differing across metric rows, duplicate excluded observations,
summary/evidence consistency, eligibility of both comparison sides, and policy
validation across all suites before effects. Fix pass added both TOOL_METRICS
verify coverage, invalid baseline summary statistics, strict row-evidence typing,
and lint/complexity corrections. No blocking findings remain against this slice.

Verifier results on 2026-09-17, using the existing environment without sync/install:

```bash
UV_OFFLINE=1 uv --directory /Users/jdemlow/00_Code/github/dbt-cortex-agent run --no-sync pytest -q tests/test_eval.py tests/test_eval_verify.py tests/test_mutation_targets.py tests/test_requirements_contract.py tests/test_cli.py tests/test_docs.py tests/test_eval_plan_macros.py tests/test_compatibility_snapshot.py
```

Result: **190 passed in 0.79s**. Initial focused baseline was 51 passed in 0.34s.
All five slice acceptance bullets above pass through the linked behavioral tests
in `tests/test_cases.md`. Ruff check passed; Ruff format check reported 11 files
already formatted; mypy reported no issues in 8 evaluation source files.
`git diff --check` passed. Task 1 implementation files were not edited by this
slice; shared governance additions preserve its entries.

No network, Snowflake, install, commit, branch, baseline policy ratchet, or
unrelated task execution occurred. dbt parse/compile, independent review, full
package/release qualification, and live acceptance criteria are not claimed.
Compact baselines retain their existing row-free shape, so historical per-row
completeness cannot be re-proven from them. Legacy candidates without complete
row evidence now fail validation. Entirely absent boundary refs fail closed.

Additional closeout check: requirements/docs/public-content pytest returned
**1 failed, 16 passed in 0.45s**. The public-content tree scan failed before
reading files because its `git ls-files --cached --others --exclude-standard`
subprocess exited 1. An isolated public-content rerun reproduced it
(**1 failed, 2 passed in 0.20s**). This check is not claimed passing and its
unrelated test/environment behavior was not modified. Final `git diff --check`
passed separately.

## Task 4 Skill Hardening Supplement (2026-09-17)

Status: locally verified; no live qualification. This slice follows
the user's explicit task 4 scope, not an unavailable plan file. Task 1/2/3 changes
must remain intact. Historical release evidence does not qualify this slice.

### Objective And Business Context

Operators can discover the intended local skills before deployment, run skill
operations under the approved role, and recover honestly from partial uploads.
Levers are manifest declaration validation, role forwarding, and durable phase
evidence. Data is the existing manifest, local SKILL.md files, and synthetic
subprocess/runtime fixtures. Assembly line: resolve metadata, compare readable
spec declarations, validate local files, preflight every stage, copy in order,
then delegate deployment or separately smoke runtime behavior.

### Slice Acceptance Criteria

- Local planning uses explicit `config.meta.cortex_agent.skills` (also dbt's
  top-level node `meta` representation), without requiring compiled_code.
  Native model YAML uses top-level `skills`, not `capabilities.skills`.
- Detectable skills without metadata, malformed or unresolved declarations,
  duplicate names, and readable YAML/metadata name/type/path mismatches fail
  before uploads. Fully rendered YAML/JSON is comparison evidence only, not a
  fallback upload authority. Skills-free models remain valid.
- Stage DESCRIBE, stage copy, and skill runtime receive the same resolved role
  override already supplied to dbt and general Agent runtime.
- Both standalone upload and deploy retain completed destinations and the
  failed destination on later-copy errors, stop before subsequent copy/build,
  and exit 2 with structured evidence. A failed copy can have partial effects;
  output does not claim rollback or per-file atomicity.
- Focused offline behavioral tests cover discovery, YAML/metadata parity,
  unresolved/mismatched declarations, role override, and later-copy failures.

### User Stories, Dependencies, And Scope

As an adopter, fresh parse cannot silently omit my locally managed skills. As
an operator, approval of a role applies to every skill client, and partial
failure tells me which destinations need inspection.
Dependencies: existing manifest selection, execution context, stage validators,
and durable outcome domain types. No new deployment authority, macro/model
changes, stage provisioning, live execution, paid evaluation, task 1/2/3 rework,
install, network, commit, or branch is in scope.

### Notes And Verification

User authorized the conservative explicit metadata contract. Python does not
render Jinja. Opaque macro-generated declarations cannot be proven equivalent
from an uncompiled manifest; authors must maintain metadata and review dbt's
compiled native spec separately. No compiled artifact freshness claim is made
for --no-parse fixtures. Maker, critic, fix, and verifier will be local passes;
no independent subagent tool is available. Initial focused baseline:
84 passed in 3.92s.

Critic/fix pass: initial behavioral failures exposed a missed skill-named macro
and lost TimeoutExpired evidence; both were fixed. Timeout classification is
local to skill subprocess boundaries, not a change to global error semantics.
Added later-stage preflight, programming-defect propagation, preview-no-effects,
and successful-upload evidence surviving later dbt failure checks. Compiled
instruction placeholders remain valid; unresolved skill fields fail. Restored
the pre-existing task 3 phase-parser formatting to avoid unrelated churn.
No blocking findings remain against this bounded slice. This is a same-agent
critique, not an independent review.

Verifier on 2026-09-17:

```bash
UV_OFFLINE=1 uv --directory /Users/jdemlow/00_Code/github/dbt-cortex-agent run --no-sync pytest -q tests/test_skills.py tests/test_manifest.py tests/test_invoke.py tests/test_deployment.py tests/test_agent_commands.py tests/test_execution_context.py tests/test_cli.py tests/test_docs.py tests/test_requirements_contract.py tests/test_fresh_manifest.py tests/test_identity_macros.py tests/test_materialization.py tests/test_lifecycle.py tests/test_eval.py tests/test_eval_verify.py tests/test_mutation_targets.py tests/test_domain.py tests/test_compatibility_snapshot.py
```

Result: **444 passed in 7.84s**. Ruff check passed for six changed source files
and `tests/test_skills.py`; mypy reported no issues in those six source files.
`git diff --check` passed. Each slice acceptance criterion has focused behavioral
coverage linked from the test cases; prior task 1/2/3 focused tests also pass.

No network, install, Snowflake, live eval, commit, branch, release, or baseline
change occurred. No live dbt parse/compile, stage transfer, runtime, independent
review, full-suite, or exact-wheel qualification is claimed. Stage preflight
proves only DESCRIBE accessibility in these mocked tests, not write privileges.
Uncompiled Jinja skill detection is deliberately conservative (text containing
`skills` with no nonempty metadata fails, even if it was prose); opaque macros
without that signal can escape detection. Review native dbt compile output to
verify parity for those models. Failed copy means completion is unconfirmed,
not that no files were written; destination outcomes are CLI output, not a
persisted journal or per-file reconciliation.

## Review Blocker: Mutable Evaluation Annotation (2026-09-18)

Status: locally verified; no live qualification.

Objective/business context: rebuilding an evaluation source while a run is in
flight must not hide an originally in-scope failing tool score or authorize a
green release gate. Levers are source validation, immutable local annotation,
drift checks and candidate evidence. Existing cursor fixtures provide the data;
the assembly line is build source, validate/capture mapping, check before START,
start/poll/fetch against that mapping, check drift, then validate candidate.

Slice acceptance criteria (extend AC 6, 7 and 9):

- Capture all input/ref/test_type entries before START, validate unique nonblank
  inputs/refs/types and exact plan refs/cardinality, and never reread source data
  to annotate fetched observations or result-fetch retries.
- Compare source mapping before every START and after polling/result collection.
  Observed pre-START drift stops the run; observed later drift fails indeterminate
  without rebinding annotations or automatically retrying onto a new source.
- A same-input/same-ref in_scope-to-boundary change cannot exclude a failing
  tool score. Cover both tool metrics, fetch retries, run retries, malformed source
  mappings, and genuine boundary exclusions with offline behavioral tests.
- New candidates retain the mapping and source-drift flag, with artifact validation
  binding result input/ref/type annotations to that mapping. Preserve older v2
  readers/artifacts without inventing retrospective snapshot evidence; document
  compatibility and the race limits explicitly.

User story: as a release operator, concurrent source rebuilds cannot change which
evaluated tool observations count toward my gate.

Dependencies: existing dataset validator, native START/STATUS/result API, and
candidate/eligibility validators. Out of scope: new remote snapshot objects or
locks, SQL/macro/model changes, policy ratchets, installs, network, live SQL,
paid evaluations, commits, and unrelated prior edits.

Notes: native dataset ingestion is initiated by START using the source table in
the existing structured configuration; there is no separate Python dataset-create
operation. Before/after observations do not provide transaction isolation, prove
native ingestion used one version, or detect change-and-revert between reads.
Snapshots bind annotation only, not all OUTPUT content. Additive run metadata
preserves schema v2 compatibility; older artifacts without the mapping retain
their existing validation, but cannot establish immutable annotation provenance.
Compact baselines retain run metadata but still omit scored rows. Maker, critic,
fix and verifier are separate local passes by this agent; no independent subagent
tool is available. Offline tests substitute for no live operation; dbt compilation
and native ingestion behavior are not qualified by this Python-only slice.

Critic/fix pass: retained original annotations on all fetch attempts, checked
drift after failed/partial runs before retry, treated malformed post-run mappings
as drift, and verified persisted annotations against the mapping. The initial
new gate tests incorrectly omitted the required baseline; test setup was fixed
without changing the gate API. Removed the separate identity-only SELECT in
favor of the complete mapping read. Corrected the synthetic one-row cursor's
count (previously two) and kept the two-row fixture's count explicit. Lint's
complexity finding was resolved by extracting the pre-START provenance check;
one new assertion was reformatted. No blocking findings remain in the same-agent
critique against these bounded criteria; independent review is not claimed.

Verifier on 2026-09-18:

```bash
PATH="/Library/Developer/CommandLineTools/usr/bin:$PATH" UV_OFFLINE=1 uv --directory /Users/jdemlow/00_Code/github/dbt-cortex-agent run --no-sync pytest -q tests/test_eval.py tests/test_eval_verify.py tests/test_mutation_targets.py tests/test_requirements_contract.py tests/test_cli.py tests/test_docs.py tests/test_eval_plan_macros.py tests/test_compatibility_snapshot.py tests/test_agent_commands.py tests/test_lifecycle.py
```

Result: **330 passed in 1.48s**. All four slice acceptance bullets have local
behavioral coverage listed in `tests/test_cases.md`. Final Ruff lint passed;
Ruff format check reported four files already formatted, mypy found no issues
in three changed source files, and `git diff --check` passed. Prior edits remain
in place. No network, dependency install, live SQL, paid evaluation, dbt
parse/compile, commit, branch, baseline policy movement, full-suite run or release
qualification occurred. A source-query failure still exits as infrastructure
failure without a new candidate; no remote cancellation or rollback is claimed.