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
14. The final unchanged deployment proves no V3 or unnecessary routing churn when the model alias already matches; requested alias reconciliation may restore a displaced model alias.

## Evidence

Offline qualification on 2026-08-28 verifies immutable selectors, guarded
routing plans, partial alias/DEFAULT outcomes, reserved-alias rejection, stale
state rejection, and retry convergence. The historical report states that live
replay completed with distinct V1/V2 promotion, rollback, exact-version smoke,
roll-forward, and unchanged-deploy no-V3 evidence. Task 6 has not independently
verified a retained run artifact or repeated that replay on the current tree.

`TC-025-01` through `TC-025-14` in `tests/test_cases.md`.

## Task 3 Alias Documentation and Lifecycle Test Slice (2026-10-29)

Objective: operators understand the interaction between explicit custom-alias
promotion and subsequent model-alias reconciliation, without mistaking content
idempotency for independent alias coexistence or serving DEFAULT movement.

Acceptance criteria for this narrow extension of AC 4/10/14 and REQ-023 AC 7/9:

- Reuse the persistent deployment fixture and actual Jinja deploy, routing,
  inspection and reconciliation macros, not stubbed lifecycle helpers.
- Model the prior reported native observation: assigning PRODUCTION to V2
  displaces its model LATEST alias; restoring LATEST displaces PRODUCTION. The
  simulator permits one custom alias per version, separately from reserved routes.
- Explicitly pin DEFAULT to V1, deploy distinct V2 content, promote its custom
  alias without setting DEFAULT, and redeploy unchanged V2 with alias reconciliation
  enabled and disabled. Preserve V1 DEFAULT and immutable content; create no V3.
- Once LATEST is restored, an additional identical deploy emits no mutations.
- Warn in the developer guide about `--alias production` and subsequent deploys;
  reference that warning from lifecycle guidance. Distinguish the prior observed
  unversioned DESCRIBE DEFAULT specification from the editable LIVE specification.

Business context: the old dictionary-add fixture could falsely imply that custom
aliases coexist independently on one version. Levers: fixture state and public
guidance only. Data: the user's prior native observation plus synthetic V1/V2,
managed hashes, explicit pin state and recorded query effects. Assembly line:
deploy V1 -> pin DEFAULT -> deploy V2 -> promote -> inspect -> no-change deploy
-> restore model alias -> repeat and verify no churn.

User story: an operator can reconcile the model alias deliberately while keeping
the explicitly pinned serving version, and inspect the intended version rather
than infer failed deployment from an unversioned specification read.

Dependencies: REQ-023 and the existing `tests/conftest.py` macro harness.
Out of scope: production behavior changes unless a test exposes a bug, schema/gate
work, other Agent modules, native SQL, network, installs, git mutation or release.
This is documentation/test fidelity, not a new requirement or a platform-wide
single-alias guarantee. Prior native observations are supplied evidence, not a
native run performed in this slice. DEFAULT durability here is simulated.

Notes: preserve runtime/question-floor dirty changes. Maker, critic, fix and
verifier passes are sequential local passes, not independent subagents. The
offline verifier runs focused tests; actual dbt parse/compile, installed-consumer
and current native qualification remain outside this approved slice.

### Local Review and Verification

All five slice criteria have local evidence in the combined parameterized
lifecycle test and focused docs contract. The critic identified an unsupported
project-variable claim in the draft guidance; the fix documents actual code:
the materialization always passes `reconcile_alias=true`, while only the
lower-level helper permits false on unchanged content. The test uses distinct
specifications with explicit orchestration and verifies their real managed MD5
hashes, not a constant hash. No production macro bug or remaining blocker
against this bounded slice was found in the sequential local review.

Using `UV_OFFLINE=1 uv --directory <product-checkout> run --no-sync`:

- Focused pytest: **251 passed in 38.70s** across `tests/test_deployment.py`,
  `tests/test_identity_macros.py`, `tests/test_materialization.py`,
  `tests/test_lifecycle.py`, `tests/test_docs.py` and
  `tests/test_requirements_contract.py`. The new lifecycle test has two cases
  (`reconcile_alias=false/true`); the new docs test adds one case.
- Changed-test Ruff check and format check passed; `git diff --check` passed.
- Earlier deployment/docs run: 98 passed, before the guidance correction.

This is offline simulator and documentation evidence, not full-suite, actual
dbt parse/compile, native SQL/DESCRIBE, runtime, current-wheel or platform-wide
qualification. No installs, network, SQL execution, git mutation, product macro
changes or other Agent-module changes occurred. Existing runtime/question-floor
work was preserved. REQ-025/023 remain in progress; no new REQ was created.