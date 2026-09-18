# REQ-025: Immutable Agent Version Promotion, Rollback, and Recovery

**Status:** In progress; historical `0.0.6` live report retained, current routing/live proof gaps in `tests/requirement_evidence.json`.

## Summary

Expose inspectable, package-native routing over immutable Snowflake Agent versions. Promotion and rollback move aliases and optionally DEFAULT; they do not mutate version specifications.

## Acceptance Criteria

1. `agent versions` returns ordered committed versions, aliases, DEFAULT, LAST, and LIVE presence without mutation.
2. Offline preview validates Agent identity, target-version syntax, alias, allowlists, and requested DEFAULT behavior without connection or mutation; apply validates target-version existence before mutation.
3. Apply delegates every Agent DDL statement to dbt macros; Python contains no Agent DDL.
4. Promotion or rollback moves the named alias but leaves DEFAULT unchanged unless `--set-default` is explicit.
5. `--set-default` moves and verifies DEFAULT against newly inspected Snowflake state.
6. Rollback preserves all newer committed versions and creates no version.
7. Roll-forward reuses the selected existing version and creates no version.
8. `agent smoke --version` supports a committed version, alias, DEFAULT, and LIVE and reports requested and resolved provenance.
9. Evaluation captures the resolved committed version immediately before START and fails indeterminate on routing drift.
10. Deployment compares desired content with managed committed content independently of serving DEFAULT.
11. Failure between alias and DEFAULT movement reports partial routing state and converges safely on retry.
12. Missing versions, unsafe aliases, unapproved resources, and stale observed routing state fail closed; postconditions detect conflicting concurrent outcomes, while the documented non-transactional alias gap remains retryable.
13. Protected proof creates behaviorally distinct V1 and V2, promotes V2, rolls back V1, rolls forward V2, and verifies each direct and routed invocation.
14. The final unchanged deployment proves no V3 or routing churn.

## Evidence

Offline qualification on 2026-08-28 verifies immutable selectors, guarded
routing plans, partial alias/DEFAULT outcomes, reserved-alias rejection, stale
state rejection, and retry convergence. The historical report states that live
replay completed with distinct V1/V2 promotion, rollback, exact-version smoke,
roll-forward, and unchanged-deploy no-V3 evidence. Task 6 has not independently
verified a retained run artifact or repeated that replay on the current tree.

`TC-025-01` through `TC-025-14` in `tests/test_cases.md`.