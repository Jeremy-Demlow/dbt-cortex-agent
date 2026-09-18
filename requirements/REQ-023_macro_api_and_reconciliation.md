# REQ-023: dbt Macro API, Safety, and Reconciliation

**Status:** In progress; task 3 locally verified, historical `0.0.6` live evidence does not qualify new changes. See `tests/requirement_evidence.json` gaps.

## Summary

Replace the interleaved macro implementation with one minimal public API and a restartable reconciliation process that treats Agent DDL as non-transactional.

## Acceptance Criteria

1. A documented minimal public macro surface is invoked successfully from an installed consumer project.
2. Identifier, policy, Agent contract, state inspection, reconciliation, version routing, evaluation planning, runtime, and gating concerns are separated into focused macros.
3. SQL-bearing values are validated or safely serialized at their boundary; raw user strings are not concatenated into executable SQL.
4. The materialization does not switch session roles; the approved invoking connection role is authoritative.
5. Pre/post hooks and `adapter.commit()` are not described or relied on as rollback for Agent DDL.
6. Reconciliation inspects current Agent, committed versions, aliases, DEFAULT, LAST, LIVE, and managed content metadata before mutation.
7. Changed content commits exactly one immutable version; unchanged content commits none, even when DEFAULT intentionally points to an older version.
8. A failure after a durable phase emits enough state for a retry to resume without another content version.
9. Alias/default, profile/comment, MCP, grants, and LIVE reconciliation are independently retryable and verified after application.
10. Evaluation plans bind exact result identity, stable refs, target context, policy, and pre-START Agent version provenance.
11. Native evaluation never replaces an existing result table or silently collides normalized run identities.
12. All orphaned `cortex_agent__legacy_*` macros and fictional public API documentation are removed after active behavior characterization passes.

## Evidence

Offline qualification on 2026-08-28 includes dbt 1.10/1.11 installed-wheel
verification, materialization contract tests, and structured reconciliation
phase parsing from successful and failed dbt output. Live lifecycle replay is
completed with the same exact wheel.

`TC-023-01` through `TC-023-12` in `tests/test_cases.md`.

## Task 3 Hardening Supplement

Status: locally verified; historical qualification above does not qualify this
slice for live deployment or release.

Objective: operators can recover from interrupted deployment or retirement
without redundant content versions, serving DEFAULT movement, or lost evidence
of work already completed. This is task 3 only; task 1/2 changes are preserved.

Business context: Agent DDL is non-transactional. A missing LIVE draft after a
commit and an unavailable post-DROP inspection must not masquerade as a clean
no-op or erase acknowledged effects.

Levers: existing dbt reconciliation, phase markers, Python outcome parsing, and
retirement output. Data/proof: the existing Jinja behavior harness, synthetic
version state, recorded SQL effects, and controlled subprocess failures.
Assembly line: inspect state, reconcile only missing work, retain acknowledged
phases, verify postconditions, retry against the resulting state.

Slice acceptance criteria:
- Matching managed content repairs missing LIVE and verifies presence before
  success, without COMMIT or DEFAULT movement; an existing draft is not replaced.
- A failure after commit/alias or during LIVE repair/verification retains prior
  effects; retry converges without an additional immutable version.
- Deploy output retains each physical Agent's phase independently, deduplicating
  only identical Agent/phase pairs. Legacy unscoped markers stay unscoped.
- Retirement retains pre-DROP inventory and acknowledged DROP completion when
  verification fails. An unacknowledged effect is unknown, never claimed completed;
  controlled partial retirement exits 2 and an absent-Agent retry succeeds.
- The invoking role, task 1 identity checks, and shared controlled-error contract
  remain intact. Programming errors propagate, including during failure handling.

User stories: an operator can identify which Agent completed a phase, repair LIVE
after an interrupted deploy, and distinguish a completed retirement statement
from an unknown outcome without deleting retained dependencies.

Dependencies: REQ-022, REQ-026, REQ-031, REQ-032 and `tests/conftest.py`.
Out of scope: task 1/2 redesign, new lifecycle authorities, role switching,
MCP/grant/profile redesign, baseline changes, installs, network, live Snowflake,
git commits/branches, and release qualification.

Notes: use an additive optional `agent_fqn` on phase outcomes and structured
markers; do not infer Agent identity for legacy markers. Retirement evidence
distinguishes statement acknowledgement from postcondition verification, not
transaction rollback. Reuse the existing Jinja harness, not another interpreter.
Maker, critic, fix, and local verifier passes are required; no separate subagent
tool is available, so these are explicit sequential passes in this session.
Live dbt/Snowflake verification remains unperformed under the approved boundary.

### Local Verification Results

Maker/critic/fix/verifier passes were performed sequentially in this session,
not by independent subagents. Critique fixes added direct mutation guards to the
shared LIVE helper and made retirement evidence merging preserve known post-state
when older markers recur in stderr. The test SQL simulator was split into read
and mutation handlers to satisfy the existing complexity gate without exemptions.
No remaining blocking findings against this slice's acceptance criteria were
identified in that local review.

All commands used `UV_OFFLINE=1 uv --directory
/Users/jdemlow/00_Code/github/dbt-cortex-agent run --no-sync`:

- Final focused pytest: **343 passed in 6.10s** across `test_deployment.py`,
  `test_identity_macros.py`, `test_materialization.py`, `test_lifecycle.py`,
  `test_agent_commands.py`, `test_domain.py`, `test_fresh_manifest.py`,
  `test_eval.py`, `test_eval_verify.py`, `test_execution_context.py`,
  `test_mutation_targets.py`, `test_compatibility_snapshot.py`,
  `test_requirements_contract.py`, and `test_eval_plan_macros.py` in `tests/`.
- Ruff check: passed for the four changed production Python modules and five
  touched Python test files.
- mypy: success, no issues in the four changed production modules (`domain`,
  `deployment`, `lifecycle`, `commands/agent`).
- `git diff --check`: passed. Existing task 1/2 edits were retained.
- Earlier runs: 123 and 318 tests passed; the initial lint run reported test
  helper complexity, nested-if style, and one long line, all fixed and rechecked.

Each slice criterion above has passing local behavior evidence in the linked
task 3 test cases. This is not full-suite, installed-wheel, actual dbt
parse/compile, live Snowflake, concurrency, or release-matrix qualification.
No network, installs, Snowflake operations, commits, or branches were used.

## Independent-Review CREATE Recovery Slice (2026-09-18)

Objective: interruption after initial CREATE cannot silently mint a duplicate
content version on retry. Extends AC 7/8 while preserving task 1-7 behavior.

Acceptance criteria:

- An absent Agent creates one initial immutable version and no extra COMMIT;
  successful retries reuse its managed hash and preserve DEFAULT.
- Lost CREATE acknowledgement, failed alias inspection, or failed initial
  version-comment write leaves a recognizable package-created Agent. Retry
  fails closed before LIVE/spec/COMMIT/alias changes, including forced retries.
- Do not infer the immutable version's specification or historical staged skill
  content from current desired content, current LIST results, or DEFAULT alone.
  Both unchanged and changed current skill hashes must remain blocked.
- Existing intentional external-Agent adoption remains supported: an existing
  Agent without the package's creation marker follows the existing LIVE/COMMIT
  path. Successfully marked initial versions retain automatic reconciliation.

Levers/data/assembly line: inspect the existing package CREATE object comment
and initial version metadata in the stateful native-query simulator; detect
unfinished creation -> stop -> require explicit operator recovery. No second
Python lifecycle or guessed native spec normalization is introduced.

Decision: choose the explicitly permitted fail-closed recovery rather than
automatic adoption of an unmarked immutable version. The existing CREATE marker
is retained, including for interrupted pre-fix creations. It is a recovery
signal, not proof of exact spec or historical stage content. Unknown inspection
results fail closed. `force_agent_recreate` does not bypass this stop.

Recovery requires operator inspection of native immutable specifications and
historical skill content evidence. If equivalence cannot be established, no
hash comment should be invented; explicitly approved retirement/recreation is
an option only after reviewing history, grants and routing loss. Automatic
recovery, external removal of the creation marker, concurrency, profile/MCP
redesign, installs, network, Snowflake, commits and branches are out of scope.

Dependencies: REQ-032 review slice and existing deployment/Jinja tests. User
story: an operator gets an explicit recovery stop instead of duplicate history
or falsely attributed exact content. Local maker/critic/fix/verifier results
are recorded below; no independent subagent or live qualification is claimed.

### CREATE Review Verification

All four slice acceptance criteria have local behavioral evidence in
`tests/test_deployment.py`: absent-Agent success/repeat, lost CREATE and metadata
acknowledgements, failed inspection/comment write, unknown native metadata,
unchanged/changed desired specification and current skill hashes, forced retry,
post-metadata alias/LIVE recovery, and preserved external-Agent adoption.
Unmarked initial creation deliberately stops rather than auto-converging; no
exact immutable content or historical stage equivalence is inferred.

Local maker/critic/fix/verifier passes completed; the critic required honest
unknown inspection handling and explicit distinction between persisted metadata
and missing metadata. No remaining blocker against this bounded slice was found.
The final shared run with REQ-032 passed **631 tests in 16.31s**, plus changed-file
Ruff and the configured deployment mypy check. See REQ-032 for commands, file
scope and the unrelated pre-existing runner typing failure from broader mypy.
No live Snowflake, compilation, installation, network, commit or branch occurred.
Automatic unmarked-version recovery and current exact-wheel live qualification
remain open; broad REQ-023 completion is not claimed.