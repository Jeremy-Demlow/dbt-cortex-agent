# REQ-014: installed-wheel single-Agent verifier

## Status

Complete.

## Summary

Verify the built Python wheel and the matching dbt package together from outside the source
checkout against two isolated, credential-free consumer projects: one Agent-only project and one
project with an optional evaluation suite for that same Agent.

## Business context

Unit, macro, and documentation contracts prove individual boundaries, but the release gate does not
currently exercise the installed wheel through the complete adopter preview sequence. A packaged
starter regression could therefore pass source-checkout tests while failing after installation, or
could accidentally make evaluation metadata a deployment prerequisite or restore a second physical
Agent identity.

## Objective

A maintainer can reject a wheel before release when an isolated adopter cannot complete the full
non-mutating single-Agent preview path, so the distributed CLI and dbt package prove one physical
Agent with evaluation remaining optional.

## Acceptance criteria

1. One deterministic verifier creates its own virtual environment, installs the supplied wheel and
   an explicitly selected supported dbt Core/dbt-snowflake line, and executes outside the source
   checkout with no source-tree Python import.
2. The verifier copies the matching dbt package into its isolated workspace and creates two separate
   consumer projects from installed starter data. Neither consumer dependency nor command working
   directory points into the source checkout.
3. Project A removes all optional eval model/metadata and completes dependency resolution, offline
   parse, doctor, manifest validation, Agent render, deploy preview, and smoke preview. Doctor and
   the manifest prove zero enabled evals, and no eval command or eval macro is required.
4. Project B retains the optional unsuffixed eval suite and completes the same sequence plus eval
   plan preview. Render, deploy preview, smoke preview, and eval plan report the same Agent FQN.
5. Both projects expose the `single_agent` lifecycle contract, contain no projection field or
   `_EVAL` physical identity, and render the same Agent specification.
6. Eval preview is non-paid and invokes only fresh parse plus `cortex_eval__execution_plan`; it does
   not invoke any Agent lifecycle macro, alter the render artifact, connect through Snow CLI, deploy,
   invoke runtime, accept a baseline, or mutate Snowflake.
7. Script unit tests cover isolated project construction, command/result validation, prohibited
   projection and lifecycle evidence, and fail-closed command errors without creating a venv or
   accessing the network.
8. Static workflow tests require the installed-wheel verifier in package CI, preserve the supported
   Python 3.10/3.11/3.12/3.13 test matrix, and run the verifier for dbt 1.10 and 1.11 where the dbt
   compatibility matrix is authoritative.
9. The release workflow remains publication-safe: manual dispatch cannot publish, only the protected
   publish job has OIDC permission, and no credential, Snowflake, runtime, mutation, paid eval, or
   baseline action is introduced.
10. Local verification runs the verifier, focused and full tests, build, Twine, exact wheel inventory,
    workflow YAML parsing, and patch hygiene. It records unavailable interpreter matrix evidence
    honestly and performs no consumer edit, Snowflake operation, commit, or push.

## User stories

- As a release operator, I can prove the exact installed wheel works with the supported dbt lines
  before publication.
- As a new adopter, I can complete the Agent-only path without adding or running an evaluation.
- As an evaluation author, I can add an optional suite and prove it plans against the same Agent FQN
  without causing deployment.
- As a security or cost reviewer, I can inspect deterministic evidence that the verifier stays outside
  connector, mutation, runtime, paid evaluation, and baseline boundaries.

## Dependencies

- REQ-008 standalone CI and release verification.
- REQ-010 trusted PyPI publishing.
- REQ-011 tutorial product readiness.
- REQ-013 single physical Agent evaluation.

## Out of scope

- Snowflake credentials, connections, deployments, runtime invocation, or paid Agent Evaluation.
- Consumer repository edits, baseline creation or movement, release publication, commit, or push.
- Expanding the supported Python or dbt version ranges.

## Notes

- Objective lever: make the installed artifact execute the exact non-mutating adopter assembly line,
  rather than treating wheel import/help checks as end-to-end package evidence.
- Data: the packaged Orders starter already supplies one exposure and one removable optional eval
  suite; package CI already defines Python 3.10-3.13 and dbt 1.10/1.11 authority matrices.
- Assembly line: build wheel -> isolated wheel install -> isolated dbt package copy -> two consumer
  projects -> deps/parse/doctor/manifest -> render/deploy/smoke previews -> optional eval plan ->
  cross-output identity and no-side-effect assertions.
- Reversible local choice: package CI runs the end-to-end verifier in the two-entry dbt compatibility
  matrix on Python 3.11, while the existing four-entry Python matrix remains the interpreter proof.
- Verifier: mandatory because this slice changes executable package and workflow verification.
- Critic record (2026-08-10): the first pass found three blocking defects: unit fixtures treated
  smoke's documented physical object name as a full FQN; matrix builds wrote `dist/` before a
  `git status` assertion in the full suite; and command safety rejected the local-only starter
  `init --apply` needed to construct packaged fixtures. The fix compares smoke's object component
  to the rendered FQN, builds matrix wheels under `RUNNER_TEMP`, and permits `--apply` only for
  `init` while rejecting it for every Snowflake/runtime/eval command. No blocking finding remains.
- Verifier record (2026-08-10): the complete 316-test package suite passed. The exact built wheel
  completed both isolated projects on dbt Core `~=1.10.0`/dbt-snowflake `1.10.3` and dbt Core
  `~=1.11.0`/dbt-snowflake `1.11.4`; each run proved zero evals for Agent-only, one optional eval for
  Agent-plus-eval, one FQN, no projection or `_EVAL`, no lifecycle macro during eval planning, and
  no paid apply. Sdist/wheel build, Twine, exact inventory, two-workflow YAML parse, and
  `git diff --check` passed. The existing Python 3.10-3.13 workflow matrix was preserved; only the
  local Python 3.13 interpreter was exercised in this run. No connector, Snowflake mutation/runtime,
  paid evaluation, baseline action, consumer edit, commit, or push ran.
- Independent candidate review (2026-08-10): command safety now permits `--apply` only for the exact
  installed `dbt-cortex-agent init` fixture-construction command, rejects direct Snow CLI execution,
  and uses a valid single-command CI residue cleanup. Focused tests cover the rejected command shapes.
- Independent verifier record (2026-08-10): the exact wheel passed both dbt Core `~=1.10.0` with
  dbt-snowflake `1.10.3` and dbt Core `~=1.11.0` with dbt-snowflake `1.11.4`. The 320-test suite
  passed on local Python 3.10, 3.11, and 3.13; Python 3.12 was unavailable locally but remains in
  the unchanged CI matrix. Build, Twine, wheel inventory, all YAML/workflow parsing, tracked-file
  secret scan, byte compilation, patch hygiene, and residue cleanup passed.
