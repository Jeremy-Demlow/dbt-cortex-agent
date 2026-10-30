# REQ-034: Opt-in per-question metric floors

**Status:** Offline-preview blocker locally corrected and verified; 0.0.12 release pending, native policy qualification not claimed.

## Summary

Add generic, dbt-owned `questions[].thresholds` maps keyed by declared metric
names. Resolve them by stable `ground_truth_ref`, never by question text or
native record IDs. Existing suites without nonempty question thresholds retain
their current signature and schema-v2 behavior.

## Business Context

A good suite average can hide a poor answer to a critical question. Release
owners need selected questions to block acceptance even when averages pass.

## Objective

An Agent that fails an explicitly protected question cannot pass verification,
comparison, gating, or baseline acceptance on the strength of other answers.

## Acceptance Criteria

1. dbt validates and renders opt-in question floors by unique declared refs and
   metrics; finite floors fall within system metric bounds or explicit ordered
   custom score ranges. Tool floors on non-in-scope questions are rejected.
2. The validated policy participates in the suite signature and versioned plan,
   candidates, and baselines. Absent/empty policy retains legacy schema/signature;
   existing evidence is not rewritten or silently upgraded.
3. Python checks each protected ref/metric against complete finite applicable row
   evidence, rejects out-of-range scores and source applicability disagreement,
   and cannot pass from mutable summaries, stored failure lists, or passed flags.
4. Compare/gate/baseline acceptance/verify enforce the same floors. Changed,
   lowered, removed, or differently keyed policies are incomparable; verify binds
   policy to the current dbt plan. Protected baselines retain scored row evidence.
5. Native macro run and gate fail closed for this policy before START or result
   reads, explicitly directing users to the Python CLI. Native run/start dry runs
   and explicit renderer previews issue zero queries even with dbt `execute=true`
   and live checks requested. Preview dataset hashes/existence remain unresolved
   and output is labelled non-executable; normal rendering retains real hashing.
6. Focused offline tests and documentation explain the opt-in contract,
   compatibility, evidence limitations, native boundary, and pending qualification.

## User Stories

- As a release owner, I can protect a critical question without replacing the
  suite-wide averages or changing other suites.
- As a baseline owner, a candidate cannot lower a protected floor to pass.
- As an auditor, I can replay protected candidate and baseline decisions from
  retained rows rather than trust a summary or historical pass flag.
- As an operator, I can preview the real native call chain without inspecting
  Snowflake or mistaking an unknown dataset identity for an executable config.

## Dependencies

- REQ-005 execution-plan authority and stable ground-truth refs.
- Existing dataset snapshots, row completeness, verify binding and baseline gates.
- REQ-029 native macro boundary.

## Out of Scope

Live evaluation, SQL execution, deployment, release version changes, publication,
baseline movement, adopter edits, alias fixtures, and native per-row SQL gating.

## Notes

- The separately approved 2026-10-30 release-finalization slice in REQ-021
  restores the exact declared requirements allowlist, including REQ-033/034.
  Normal parent staging is now possible without force-add. The earlier ignore
  preservation and local verification records below remain historical; this
  tracking decision does not expand the policy implementation or claim native proof.
- Levers: dbt metadata validation/rendering; Python row validation and intrinsic
  eligibility; accepted-policy comparison; explicit unsupported-native guards.
- Data: existing complete ref/metric observations and pre-START input/type/ref
  snapshots supply the evidence. No domain-specific strings or datasets are needed.
- Assembly line: metadata -> validated signed plan -> snapshot applicability
  check -> evaluation observations -> intrinsic floors -> comparison/acceptance.
- Local decisions: nonempty policy uses plan/artifact v3 with a version-1
  `question_policy` containing thresholds, score bounds and declared test types.
  System bounds are [0, 1]; a gated custom metric requires explicit score ranges.
  Ungated custom metrics retain existing semantics. Empty maps are not opt-in.
- Protected baselines retain complete rows for deterministic replay; legacy v2
  baselines remain compact. Signatures are consistency checks, not cryptographic
  authenticity against an actor rewriting all evidence.
- Maker/critique/fix/verifier are local passes. Parent performs independent review.
  No dbt compile or live native qualification is authorized in this slice.
- The pre-existing `.gitignore` ignores all new requirements. This slice preserves
  it exactly, does not force-add ignored files, and leaves REQ-034 local until
  the owner chooses the tracking policy. The pre-existing ignore-contract test
  expects exceptions that the user's dirty ignore file removed; it is not repaired
  by restoring or changing the owner's edit.

## Offline-preview blocker correction (2026-10-29)

- Objective: reviewing a native evaluation preview cannot read Snowflake or
  imply that dataset identity/existence has been verified.
- Reviewer evidence: `run(dry_run=true)` called the real renderer with
  `execute_checks=false`, but content hashing and `SHOW DATASETS` still ran under
  dbt `execute=true`. The prior dry-run test replaced the renderer and did not
  prove AC5. Its earlier pass claim is superseded by this finding.
- Levers/data/assembly: propagate an optional `dry_run=false` flag through the
  real renderer/config builder from native run/start; retain local graph
  validation, then render unresolved preview metadata instead of querying.
- Slice acceptance: zero `run_query` calls through real run/start/render/build
  with `execute=true`, including requested live checks; `preview_unresolved`
  hash, null existence and non-executable label; no inferred create/reuse when
  dataset inclusion is unspecified; normal rendering still hashes content and
  inspects inventory; execution-plan signatures and alias/lifecycle behavior
  remain unchanged.
- Local choice: append optional parameters so existing positional calls remain
  valid. Preview metadata is not a signed execution plan or native START config;
  omitted dataset inclusion represents an unknown create/reuse choice. Explicit
  inclusion remains a requested shape, never evidence of existence.
- Maker/critic/fix/verifier are separate local passes. Verification uses real
  Jinja call chains with a query spy, not a replaced renderer. No dbt compile,
  SQL, network, git mutation, native proof, or baseline movement is authorized.

### Correction review and verification

- Maker: the strengthened regression failed at the real content-hash query
  before the fix. Added preview propagation and explicit unresolved metadata;
  normal `execute=true` rendering retains the original native config shape.
- Critic: reviewed the real helper graph for hidden queries, START's default
  live checks, unknown create/reuse claims, signature/alias scope, positional
  compatibility and preview acceptance. No blocking code finding remained;
  requested stronger coverage for parse-context identity, unsafe run names,
  normal START/live validation and rejection as an accepted execution plan.
- Fix: added those behavioral cases and docs assertions. No renderer, builder,
  metadata validation or graph lookup is stubbed in the preview regressions.
  Normal-path query responses are synthetic, not SQL execution.
- Verifier: 75 question-floor cases pass (44 previously, 31 net additional);
  the focused question/eval/verify/Jinja/requirement suite passes 372 cases.
  Final focused suite including documentation: **386 passed**. Scoped Ruff
  lint/format and `git diff --check` pass.
- Slice acceptance: zero-query actual previews PASS; unresolved/non-executable
  output PASS; normal hash/inventory/live checks PASS under synthetic responses;
  unchanged signed execution-plan payloads PASS for both v2 and opted-in v3;
  existing unsupported-policy run/gate guards PASS. Agent alias/lifecycle code
  and signatures were not modified.
- Verification limits: no dbt parse/compile, installation, supported-dbt matrix,
  SQL/Snowflake/network, paid/native proof, full suite or independent re-review
  was run in this correction. Local Jinja is behavioral evidence only. Existing
  ignore rules and unrelated dirty edits were preserved; REQ-034 remains ignored
  and was not force-added. Stop at this blocker correction's slice boundary.

## Earlier Local Verification (2026-10-29; AC5 superseded)

- Maker: implemented the metadata/policy/row-gate slice only; no release version,
  adopter source, ignore rules or existing evidence was changed.
- Critique/fix: inspected policy/signature/schema/row replay and public command
  boundaries. Added direct apply preflight, strict opt-in ref types, eval-run
  eligibility replay and failed baseline-preview rejection; added behavioral
  custom/tool/boundary, duplicate-ref, rekeying and native dry-run tests. No
  blocking local finding remains; this is not the parent's independent review.
- Verifier: 44 new question-floor cases pass. Focused question/eval/verify/Jinja/
  requirements suite: 341 passed. Broad offline suite: 1020 passed, 2 deselected,
  with the 12 git-mutating release fixtures explicitly ignored.
- The initial complete run was 1007 passed / 14 failed. One failure is the
  pre-existing ignore contract mismatch. The public-content child Git and 12
  release-fixture Git subprocesses failed. A read-only subprocess probe confirmed
  xcrun cannot load its ARM-only libxcrun from the x86_64 Python environment;
  no installs or environment repair were attempted. The broad result above is
  not a claim that these excluded checks passed.
- Scoped Ruff lint/format, mypy (five changed evaluation/command modules), and
  `git diff --check` pass. Jinja calls are executed locally, not source-only
  assertions; no dbt compile/SQL/Snowflake/network/install was performed.
- AC1-4: pass within the synthetic local policy/plan/row/command and explicit
  native-unsupported scope. The AC5 preview claim failed independent review;
  the correction above requires fresh verification. AC6: local tests/docs pass; full unexcluded suite,
  independent review, supported installed-dbt matrices and live qualification
  remain pending. No requirement is marked globally complete.