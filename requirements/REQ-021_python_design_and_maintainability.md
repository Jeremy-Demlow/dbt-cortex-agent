# REQ-021: Python Design and Maintainability

**Status:** In progress; historical `0.0.6` qualification retained, current coverage gaps in `tests/requirement_evidence.json`.

## Summary

Make `src/dbt_cortex_agent` a small, typed, inspectable control-plane library. Use standard-library values and protocols rather than adding fastcore as a runtime dependency, while adopting its emphasis on concise composition, deliberate APIs, and executable examples.

## Acceptance Criteria

1. External manifest, YAML, JSON, subprocess, connector, and HTTP payloads are validated at typed boundaries before domain logic uses them.
2. Snowflake identities, execution context, lifecycle phases, policies, and outcomes use immutable values with centralized validation.
3. Orchestration functions compose short single-purpose functions; command handlers do not contain reusable domain logic.
4. Expected configuration, filesystem, subprocess, connector, HTTP, and protocol failures produce categorized controlled errors without tracebacks.
5. Every subprocess and network operation has a finite, configurable bound and reports command phase without exposing secrets.
6. Public exports and function signatures are intentional, documented, and covered by installed-wheel import tests.
7. Every tracked test is collected by default; intentional live or slow exclusions use explicit markers rather than ignore paths.
8. CI enforces formatting/linting, supported Python typing, branch coverage, complexity bounds, dependency compatibility, wheel inventory, and secret scanning.
9. Property tests cover identifiers, paths, numeric policies, and protocol framing; mutation tests target safety-critical validators and gates.
10. Compatibility snapshots record the supported `0.0.5` CLI, JSON, artifact, and macro behavior before replacement work begins.

## Non-Goals

- A fastcore runtime dependency.
- A general web framework or dataframe dependency.
- Compatibility wrappers for APIs that were documented but never implemented.

## Evidence

Offline qualification on 2026-08-28: 315 tests passed with 81.35% branch
coverage; Ruff formatting/lint/C90 and mypy passed; all six bounded
safety-critical mutants were killed.

`TC-021-01` through `TC-021-10` in `tests/test_cases.md`.

## 0.0.12 release-finalization slice (2026-10-30)

### Objective and business context

Consumers can follow one consistent 0.0.12 installation and operating contract,
and release reviewers can discover every explicitly approved requirement without
publishing local credentials, evidence, or unrelated ignored files.

### Slice acceptance criteria

- Restore exactly the requirements exceptions declared by
  `test_requirements_ignore_exceptions_remain_narrow`: REQ-019, REQ-021 through
  REQ-034, README and user stories. Preserve every other ignore rule.
- Align current install pins, CLI guidance, project skill and release metadata
  at Python 0.0.12 / Git v0.0.12. Preserve historical immutable-release records.
- Date the 0.0.12 changelog entry 2026-10-30 and state that publication remains
  unconfirmed until protected exact-wheel proof and PyPI publication succeed.
  Describe runtime budgets and opt-in CLI question floors as 0.0.12 interfaces,
  not as capabilities of 0.0.11. Do not claim native evaluation or answer quality.
- Run focused offline documentation, parser, inventory, requirements, runtime
  and question-policy contracts plus formatting/lint and patch hygiene. Record
  observed results separately from earlier candidate qualification.

### User story, dependencies and limits

As a release reviewer, I can stage the approved inventory normally and distinguish
release-ready instructions from completed publication evidence. This slice
depends on REQ-033/034's existing implementation and the protected release
workflow. Runtime/macro changes, adopter edits, new release automation, Git
mutation, native evaluation and baseline movement are out of scope. The parent
owns commit, push, immutable tagging, release creation and protected publication.

### Notes

- Levers: exact ignore inventory, current documentation pins and assertions.
  Data: existing version metadata, declared CI inventory and local contracts.
  Assembly: align source -> offline checks -> parent review -> protected release.
- User explicitly approved this narrow ignore repair. Earlier removed rules
  remain visible in Git history; no broad requirements or test exception is added.
- Verifier: substituted by focused offline inventory/docs/parser/policy contracts
  because this slice changes documentation and ignore configuration only, not
  SQL/macro/model logic, evaluation semantics or deploy behavior.
- Local maker/critic/fix/verifier passes are required. Their results do not
  replace the parent's independent review or remote exact-release gates.

### Local review and verification

- Maker: restored the exact inventory, dated the release-preparation entry and
  aligned current instructions and assertions at 0.0.12; runtime, macro and
  workflow behavior were not changed by this slice.
- Critic: checked private-ignore preservation, mixed install pins, historical
  release claims, schema-v2/v3 storage descriptions, native-policy boundaries,
  guide heading/linkage and whether prior candidate proof could imply final-byte
  qualification. Found an unqualified "baselines omit rows" statement and
  missing current question-policy guidance in the skill/CLI reference.
- Fix: qualified compact baselines as schema v2, retained protected-v3 row
  replay, and added the same opted-in/native-rejection contract to the skill
  and CLI reference with a documentation regression. Earlier consumer proof is
  explicitly labelled pre-finalization, not final-tag qualification.
- Verifier: **395 passed in 8.00 seconds**, across 12 focused/adjacent test files,
  with OS-level network denial. This includes docs, CI inventory, CLI, project
  skill, requirements linkage, runtime budget, question floors, invocation,
  skills, Agent commands, doctor and public-content policy. Initial focused
  seven-file run: **220 passed in 7.59 seconds**.
- Global product-root Ruff check passed; Ruff format check reported **74 files
  already formatted**; configured mypy passed for **14 source files**; patch
  hygiene passed. Read-only Git inspection confirms HEAD remains unchanged and
  no staged changes were introduced. The ignore diff against HEAD adds only
  REQ-033 and REQ-034; direct checks retain credentials/evidence/local-state and
  the historical ignored test.
- All slice-local criteria are verified; no blocking local critique remains.
  This is not independent subagent review or a complete release gate. No full
  unexcluded suite/coverage rerun, build/Twine/wheel rebuild, installed-consumer
  rerun, clean-tag preflight, secret/license/SBOM scan, remote CI, protected
  smoke, native evaluation, Git mutation or publication was performed here.
  Parent-owned final-byte checks and publication remain pending.