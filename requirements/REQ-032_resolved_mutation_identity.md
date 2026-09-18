# REQ-032: Resolved Mutation Identity

**Status:** In progress; task 1 and independent-review deployment fixes locally verified, current live qualification pending.

## Summary

Keep dbt-resolved Agent identity consistent from manifest planning through
materialization, version routing, and explicitly confirmed retirement.

## Business Context

Standard dbt schema generation may combine the target schema and custom schema.
Reusing raw config or independently consuming a stale manifest can operate on
an Agent other than the one the operator reviewed.

## Objective

An operator's approved Agent is the Agent changed, or the operation stops before
changing an Agent. dbt remains the sole Agent DDL authority.

## Levers and Data

The package controls relation selection, parse arguments, and mutation-macro
arguments/validation. Existing manifest nodes, resolved `this` relations, command
fakes, and Jinja execution provide local proof without Snowflake access. The
assembly line is resolved metadata -> bounded plan -> identity check -> dbt DDL.

## Acceptance Criteria

1. Materialization uses resolved `this` database/schema/identifier for deployment,
   comment, and profile updates under default and custom dbt naming.
2. Python routing and retirement always pass the planned physical FQN. Routing
   rejects mismatched or missing inspected identity before invoking mutations.
3. Alias, DEFAULT, composite routing, and drop macros reject a supplied mismatched
   identity before their mutation; omitted expectations preserve lower-level calls.
4. Fresh parse explicitly writes the exact consumed `manifest.json`; nonstandard
   filenames, ambiguous project target paths, parse failure, and missing/unchanged
   output fail closed. Explicit manifest location wins, otherwise environment
   target path precedes a literal project target path and the default `target`.
5. Behavioral tests execute Jinja macros and command boundaries with no network,
   Snowflake, installations, commits, branches, or changes to other plan tasks.

## User Stories

- As an adopter, custom schema naming does not separate deployed and planned Agents.
- As an operator, a changed dbt graph cannot redirect my routing or drop approval.
- As an automation author, custom artifact paths cannot silently consume stale data.

## Dependencies

Extends REQ-023, REQ-025, and REQ-026 using current manifest identity and command
runner contracts. No dependency on plan tasks 2-7; those tasks remain untouched.

## Out of Scope

Evaluation gates, retry convergence, skill contracts, runtime evidence, release
qualification, installations, remote execution, and independent subagent execution.

## Notes

- Slice-local choice: use an optional `expected_agent_fqn` in dbt macros; Python
  retirement requires it and Python routing derives it from the immutable plan.
- Pin parse output via `--target-path` and `--write-json`, preserving the child
  environment (including profile-directory selection) and project cwd. Do not
  interpret Jinja in project target paths; require an explicit manifest instead.
- Compare pre/post output file metadata to reject successful commands that did not
  rewrite the consumed artifact, including disabled artifact writes.
- No macro execution harness exists in the tracked tests at baseline 261a0b8.
  Reuse the verifier's StrictUndefined/do-extension Jinja pattern with shared
  macro-return support for the new behavior tests.
- Maker, critic, fix, and verifier passes are performed locally by the same agent;
  no independent subagent tool is available. No live proof is claimed.

## Verification

Pending focused offline pytest and local critique. dbt parse/compile and live
deployment are not claimed by these deterministic mocked-boundary tests.

## Independent-Review Blocker Slice (2026-09-18)

Objective: approval of selected Agents cannot silently authorize a different
physical Agent or an undeclared Agent ancestor. Preserve all task 1-7 work.

Acceptance criteria extending AC 1/5 and REQ-022 AC 1:

- Apply passes the planned `unique_id` -> physical FQN map through dbt `--vars`.
  Materialization validates `this` against that map before pre-hooks, stage
  inspection, or Agent DDL; an unexpected ID or invalid map fails closed.
- Planning rejects every unselected Agent ancestor, including indirect and
  metadata-disabled Agents, before skill planning/upload/build. Explicitly
  selecting ancestors includes their skills and databases in the normal plan.
- Graph drift after planning cannot redirect a selected Agent or authorize an
  unexpected Agent materialization. Direct dbt builds without a supplied map
  retain the documented lower-level behavior.

Levers/data: the existing manifest traversal, dbt command builder, resolved
`this`, and stateful Jinja test harness. Assembly line: resolve -> reject hidden
Agent closure -> preview -> forward exact identities -> check -> materialize.

Decision: use conservative ancestor rejection, explicitly authorized by the
request, rather than silently expanding approval. The internal
`cortex_agent_expected_fqns` var is an invocation-scoped mapping, not a selector
or user-maintained naming convention. Missing var preserves direct builds;
supplied empty/invalid maps do not disable the guard.

Limits: this is an Agent materialization boundary, not a transaction or a lock
on the whole dbt graph. Earlier approved skill uploads, ordinary ancestor models,
project on-run-start hooks, and other parallel nodes may already have effects.
Independent-review fixes do not make arbitrary consumer hooks safe.

Dependencies: REQ-022/023 and existing command/Jinja harnesses. Out of scope:
new deployment authority, graph locking, hooks redesign, network, installations,
Snowflake execution, baseline movement, commits, branches, and release proof.
User stories and behavioral cases are linked in their existing indexes.

Maker/critic/fix/verifier run sequentially locally; independent subagents
are unavailable. Executed verification results are recorded below.

### Review Slice Verification

Maker, adversarial critic, fix and verifier passes completed sequentially in
this session, not as independent subagents. Critique tightened null/invalid-map
handling so a supplied null cannot disable approval, covered both manifest
edge representations and metadata-disabled ancestors, and retained the explicit
non-atomic/hook/concurrency limitations. No blocking finding remains against
the three review-slice acceptance criteria; all have executed local evidence.

Final command prefix: `PATH=/Library/Developer/CommandLineTools/usr/bin:$PATH
UV_OFFLINE=1 uv --directory /Users/jdemlow/00_Code/github/dbt-cortex-agent run --no-sync`.

- **631 passed in 16.31s** across deployment, materialization, identity macros,
  Agent commands, lifecycle, skills, fresh manifest, execution context, mutation
  targets, eval, eval verify/plan macros, invocation, domain, requirements/docs,
  both verifier test modules and compatibility snapshot (19 test files).
- The existing `test_default_schema_consumer_parse_and_materialization` passed
  with locally installed dbt and a temporary consumer; no deps/install occurred.
  Agent effects remain simulated. No dbt compile or live deployment was run.
- Changed-file Ruff passed; `mypy src/dbt_cortex_agent/deployment.py` passed.
  Explicitly adding `dbt_runner.py` to mypy's scope exposes its pre-existing
  `CommandRunner.run` kwargs inference error at line 25 (confirmed in HEAD).
  That unrelated typing issue is unchanged, not a passing check.
- `git diff --check` passed. All prior task 1-7 work remains in the dirty tree.
  No network, installs, Snowflake, commits or branches were used.

This is focused offline proof, not full-suite, clean-wheel, supported-dbt matrix,
native spec equivalence, historical stage-content, concurrency or live release
qualification. The separate CREATE recovery result is recorded in REQ-023.