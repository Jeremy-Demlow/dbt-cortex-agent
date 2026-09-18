# Regression tests

## Candidate Preparation: Requirements Exceptions Removed

- Root cause: the pending ignore diff removed every historical requirements exception, hiding the new REQ-032 file from normal untracked-file discovery.
- Fix summary: restore the prior narrow allowlist and add only REQ-032; generated evidence stays ignored. Align current release surfaces at 0.0.9 without rewriting archived 0.0.8 evidence.
- Verification: `tests/test_ci.py::test_requirements_ignore_exceptions_remain_narrow` pins the exact requirements rule block; current CLI/docs/CI identity tests require the dated candidate and pending qualification/publication status.

## Final Review: HTTPError Body Leak And Inherited Proof Executable

- Root cause: `urlopen` raises an `HTTPError` that owns its body before the successful-response registration runs. The proof script also preferred inherited `DBT_EXECUTABLE` or host PATH discovery over its pinned isolated dbt, so package child commands could bypass the proof runtime.
- Fix summary: register the HTTP exception itself with the existing managed-resource stack before re-raising; retain primary identity, normalized/raw evidence, and secondary cleanup errors. Force the shared proof environment's executable to `venv/bin/dbt`, including lifecycle, guarded retirement, and cleanup-only; remove host discovery. Give the command runner's heterogeneous kwargs an explicit `dict[str, object]` annotation without ignores or execution changes.
- Verification: `test_http_error_closes_owned_body_and_retains_primary` and `test_http_error_survives_cleanup_and_artifact_write_failure` cover real stdlib error ownership with fake bodies, single explicit close, all cleanup phases, and evidence errors. `test_proof_pins_dbt_for_all_phases_despite_inherited_executable`, `test_cleanup_only_uses_same_pinned_environment_without_venv`, and `test_fake_setup_without_pinned_dbt_fails_instead_of_using_host` cover conflicting/absent overrides, isolated command/environment agreement, fake setup failure without host fallback, and independent bounded cleanup. Exact offline results are in REQ-028's final-review supplement; no live proof or clean installation is implied.

## Review Blocker: Post-Run Annotation Read Mutable Source

- Root cause: `_fetch_rows` reread current source input/ref/test_type after evaluation and on fetch retries. An in_scope-to-boundary rebuild could discard an evaluated failing tool score without changing inputs or refs.
- Fix summary: validate/capture the entire immutable mapping before START, compare before each START and after polling/fetch, annotate only from that snapshot, stop retries on observed source drift, and persist/validate mapping and drift metadata. Completed scored runs with observed drift are indeterminate and failed; source query failures remain infrastructure failures, not green evidence.
- Verification: `tests/test_eval.py` exercises both tool metrics, START/STATUS/fetch/fetch-retry changes, pre-START/run-retry drift, malformed mappings, invalid post-run sources, persisted binding and legacy-v2 compatibility. See REQ-022's review-blocker supplement for exact offline results. Checks do not freeze Snowflake ingestion, hash all OUTPUT content, or detect change-and-revert between reads; the separate native macro path is unchanged.

## Independent Review: Deploy Approval And Initial CREATE Gaps

- Root cause: deploy apply passed selectors without planned physical identities; ancestor traversal collected databases but omitted implicitly selected Agents/skills from approval; CREATE produced its first immutable version before managed hashes were written.
- Fix summary: pass invocation-scoped unique_id/FQN vars and enforce resolved `this` before Agent hooks/DDL, reject unselected Agent ancestors before skill planning, and stop retries of package-created unmarked initial versions for explicit recovery rather than guessing spec/stage provenance or minting duplicates. External unmarked Agents retain intentional adoption.
- Verification: new behavioral tests in `tests/test_deployment.py` and `tests/test_materialization.py` cover graph drift, unexpected materialization, malformed expectations, ancestor closure, absent Agents, CREATE/metadata acknowledgement loss, failed inspections/comment writes, changed current skill hashes, forced retries and existing adoption. Prior task 1-7 tests remain intact. No whole-build atomicity, automatic unmanaged-version equivalence, or live qualification is claimed.

## Task 7: Product Contracts And Release Attestation Overclaimed Proof

- Root cause: active docs invoked an absent grant macro, promised prohibited role switching and offline/no-write compilation, and omitted skill metadata from scaffold guidance. Live attestation replaced both database states with lifecycle database A, skipped writes on failures, and ignored separate cleanup-only outcomes.
- Fix summary: correct guidance without adding grants; use one sandbox/default-schema adopter path and explicit local/network/runtime/paid boundaries. Preserve both last observed Agent states and reconciliation snapshots, record independent proof/cleanup statuses on failure and cleanup-only, reject mismatched prior identity, and keep sanitized error types. Extend the existing installed-consumer verifier's resolved-schema/deploy checks.
- Verification: `tests/test_docs.py`, `tests/test_live_multi_database_verifier.py`, and `tests/test_installed_wheel_verifier.py` exercise local contracts, injected failures, and available local dbt default-schema parse plus simulated materialization effects. Clean exact-wheel installs, protected live qualification, and separate paid evaluation remain pending; neither scripts nor collected nodes are passing live evidence.

## Task 6: Comment Tokens Masqueraded As Executable Proof

- Root cause: requirements coverage concatenated Python source and accepted a `TC-*` substring, even when present only in a comment or unrelated test. Complete labels also mixed historical live reports with current unqualified changes.
- Fix summary: explicit claim/criterion/proof JSON with bounded scopes and gaps; concrete pytest function/parameter linkage through collection APIs; separate structural/behavioral/historical/pending proof kinds; compatibility/SSE fixture contracts and accurate statuses. Existing task 1-5 tests and implementation remain intact.
- Verification: `tests/test_requirements_contract.py` rejects nonexistent nodes, invalid parameter nodes, comment-only modules, missing/extra criteria, orphan/unknown proofs, misleading empty gaps, duplicate JSON keys, invalid fixture schemas and non-local references. Current-session collection is not proof execution or live qualification; exact run results are recorded in REQ-028.

## Task 5: Runtime and verification failures discarded evidence

- Root cause: verify caught only the standard exception tuple, reset candidate paths on every failure, and reopened unbound candidates for gates; runtime buffered the entire stream before normalization/writing, used only a per-operation HTTP timeout, and acquired cursors outside cleanup protection. Sequential closes could mask the primary error and skip the connection.
- Fix summary: shared controlled predicate in verify, explicit execution/gate error states, single-load current-plan binding, incremental bounded framing/normalization, monotonic budget checks and transport timeout arguments, structured runtime evidence errors, exclusive raw writes, and shared independent managed-resource cleanup for invocation and evaluation. Programming defects propagate; prior task 1-4 behavior is retained.
- Verification: task 5 behavioral tests are mapped in `tests/test_cases.md`; exact offline results and limitations are recorded in the REQ-030/031 supplements. No hard deadline, live qualification, remote cancellation, or transactional rollback is claimed. Malformed/unframed/over-limit bytes are not retained as raw parsed events.

## Task 4: Skill discovery, role, and partial upload evidence gaps

- Root cause: local planning fell back to JSON-only compiled_code although fresh parse can omit it; docs taught an unsupported capabilities.skills location; skill clients omitted the resolved role; upload exceptions discarded successful earlier destinations.
- Fix summary: require explicit manifest metadata for local uploads, compare readable native YAML/JSON, reject detectable unresolved/mismatched declarations, forward the resolved role through stage and smoke operations, and retain per-destination outcomes using the existing durable phase domain types. Failed copies may have partial effects and are not rolled back.
- Verification: behavioral tests in `tests/test_skills.py` exercise metadata-only discovery, raw/compiled YAML/JSON parity, malformed/unresolved/mismatched declarations, role override, standalone/deploy later-copy failure, and smoke role forwarding. Results and uncompiled-Jinja limitations are recorded in the REQ-022 task 4 supplement. No live proof is claimed.

## Task 3: Interrupted deploy and retirement lost recovery evidence

- Root cause: managed-version early return skipped LIVE repair; deploy markers deduplicated globally by phase; retirement discarded subprocess evidence when verification failed after a successful DROP.
- Fix summary: share LIVE repair/postcondition checks across changed and unchanged paths, carry physical FQN in structured phase markers and outcomes, and emit retirement inventory/acknowledgement before verification. Unknown effects remain unknown; acknowledged DROP remains completed even if post-state is unavailable. Partial retirement exits 2.
- Verification: `tests/test_deployment.py` and `tests/test_identity_macros.py` reuse `tests/conftest.py` to execute real Jinja with controlled failures and persistent simulated state across retries. Adjacent lifecycle/command tests cover evidence parsing and exit behavior. Assertions include unchanged DEFAULT, no redundant COMMIT, separate same-name Agent identities, and propagation of programming defects. No live proof is claimed.

## REQ-022 Task 2: Favorable partial results produced green gates

- Root cause: compare recomputed threshold/regression outcomes without candidate eligibility; completeness counted names, not finite unique observations; policy keys were not rechecked in the consumed plan or apply preflight.
- Fix summary: share strict eligibility across compare/accept/verify; validate source-annotated ref/metric grain and finite scores before aggregation; apply TOOL_METRICS boundary exclusions before completeness; reject undeclared policy keys before effects. Validate candidate summaries against row evidence and count refs, not native record IDs.
- Verification: behavioral tests in `tests/test_eval.py` and `tests/test_eval_verify.py` exercise real compare, gate, acceptance, and verify plus mocked native result fetch/run. They cover null/nonfinite/duplicate/missing/excluded results, DEFAULT drift, non-completed/failed candidates, and policy-before-effect ordering. Local test results are recorded in the REQ-022 task 2 supplement; no live execution is claimed.

## REQ-032: Planned and mutated Agent identities diverged

- Root cause: materialization rebuilt identity from raw database/schema config rather than resolved `this`; Python routing/drop forwarded only a logical name; fresh parse wrote independently of the consumed manifest path.
- Fix summary: use the resolved relation, bind planned FQNs across Python and dbt with pre-mutation checks, and pin fresh parse to the consumed manifest directory while rejecting ambiguous paths and stale output.
- Verification: `tests/test_materialization.py::test_materialization_uses_resolved_identity`, `tests/test_lifecycle.py::test_route_rejects_inspected_identity_mismatch`, `tests/test_identity_macros.py`, and `tests/test_fresh_manifest.py` execute local behavior and record effects, rather than relying on source-string assertions. No live deployment or full-plan qualification is claimed.

## REQ-017: Native evaluation ingestion could not query an Agent Search tool

- Symptom: Agent deployment, provenance, grants, preflight, and smoke succeeded, but native evaluation ingestion failed with Search error `399502`.
- Root cause: Agent grants covered the Agent object only; `tools[].search_service` was rendered into the specification without a declarative role-access contract.
- Fix summary: Cortex Search tools now support strict `access.usage_roles`, and the sandbox-guarded Agent grant lifecycle grants `USAGE` on exactly the declared Search service.
- Verification: package contract/lifecycle tests and the reference consumer preflight prove the missing Search grant blocks before paid evaluation.

## REQ-016: Evaluation role lacked Agent monitoring access

- Root cause: the package grant lifecycle modeled only `USAGE ON AGENT`, while Snowflake Agent evaluations also require `MONITOR` or `OWNERSHIP` on the evaluated Agent.
- Fix summary: Agent metadata now supports separate `access.monitor_roles`, and the existing sandbox-guarded grant macro renders/applies `MONITOR ON AGENT` alongside usage grants.
- Verification: package lifecycle tests pin the new statement type; the Orders starter and integration fixture demonstrate distinct runtime and monitor roles; the reference consumer proves the protected asynchronous evaluation path.

## Evaluation retry generated an invalid dataset identifier

- Root cause: transient retries appended `-rN` to the run name, and the same token became an unquoted Snowflake dataset identifier.
- Fix summary: retry suffixes now use `_rN`, preserving unique run names while remaining valid unquoted identifiers.
- Verification: `tests/test_eval.py::test_apply_retries_once_and_persists_candidate` pins the retry run name used by the generated dataset configuration.

## REQ-003: Bootstrap inherited maintainer-owned defaults

- Root cause: init supplied a personal Git URL, fixed revision, implicit sandbox target, empty database allowlist, and conventional schemas when adopters omitted configuration.
- Fix summary: new dependencies, deployment boundaries, allowlists, and schemas now require explicit adopter inputs; the revision alone derives from the installed package version.
- Verification: `tests/test_init.py`, `tests/test_cli.py`, and `tests/test_doctor.py` cover missing inputs, exact dependency identification, fail-closed allowlists, optional schemas, preservation, preview, apply, and diagnostics.

## REQ-004: Lifecycle and safety boundary defects

- Root cause: manifest, identity, context, artifact, smoke, SSE, and no-change alias paths each trusted partial or ambiguous inputs at different layers.
- Fix summary: centralized strict identity/path validation, fresh parse and target-database checks, explicit connection gates, versioned contained artifacts, per-Agent smoke mapping, bounded result/SSE behavior, and no-change alias reconciliation.
- Verification: manifest, CLI, deploy, skill, invoke, and eval regression tests use local manifests, command fakes, cursor fakes, and artifact fixtures; package/static/dbt parse checks run without live operations.

## REQ-005: Duplicated evaluation-plan authority and mutable policy

- Root cause: Python independently reconstructed dbt-owned Agent naming, dataset/config identity, metrics, and tolerance policy; question annotation used a lossy input-text map; provenance was captured only after the run; comparison trusted candidate tolerances.
- Fix summary: one offline dbt-rendered plan now supplies the complete execution contract, datasets require unique stable refs, pre/post DEFAULT provenance detects drift, artifact schema v2 binds evidence to a deterministic suite signature, and baseline policy controls comparison.
- Verification: macro structural tests, plan parser/runner fakes, dataset/provenance/artifact tests, compare/gate tests, full pytest/build, and integration dbt parse run without live evaluation.

## REQ-005: Paid eval context and legacy baseline integrity gaps

- Root cause: `eval run --apply` did not expose the common allowlists, connected before proving the dbt plan target/database were authorized, and did not set the dbt-resolved role; schema-v2 validation also left known legacy accepted evidence with no safe explicit migration path.
- Fix summary: eval apply now validates shared target/database allowlists before connector use and sets the signed plan role first; preview-first migration takes all current contract fields from a fresh dbt plan, preserves legacy summary/run provenance, rejects unknown shapes, and protects existing targets behind explicit apply plus force.
- Verification: parser, plan signature, pre-connector safety, SQL context order, migration preview/apply/force, provenance, policy-authority, documentation, full package, and dbt contract tests run without live Snowflake or paid evaluation.

## REQ-006: Monolithic and inconsistent CLI process contract

- Root cause: one dispatcher mixed parser construction, presentation, safety gates, manifest freshness, and all domain orchestration; duplicate connector extras and unused role configuration exposed contracts with no distinct behavior.
- Fix summary: domain command modules now register and handle bootstrap, manifest, skill, Agent, and eval commands behind one thin entry point, with stable exit codes, structured output, explicit mutation/spend help, one runtime extra, and controlled expected errors.
- Verification: CLI contract/error/help tests, domain handler tests, full pytest/build, import checks, and a clean wheel-install smoke execute without live mutation or paid evaluation.

## REQ-008: Declared Python 3.10 support was not test-runnable

- Root cause: package tests imported the Python 3.11-only `tomllib` module while package metadata declared Python `>=3.10`.
- Fix summary: the test extra installs `tomli` only below Python 3.11 and metadata-reading tests use it as a compatible fallback.
- Verification: the complete 179-test suite passes in clean Python 3.10, 3.11, and 3.13 environments; GitHub CI adds Python 3.12 coverage.

## REQ-008: Declared dbt 1.9 compatibility exceeded fixture capability

- Root cause: `require-dbt-version` accepted dbt 1.9, but dbt Core 1.9.10/dbt-snowflake 1.9.4 cannot parse the integration fixture's modern generic-test `arguments` contract.
- Fix summary: the declared floor and CI lower-bound matrix now use dbt 1.10 with dbt-snowflake 1.10.3.
- Verification: dbt Core 1.10.22/dbt-snowflake 1.10.3 and authority dbt Core 1.11.11/dbt-snowflake 1.11.4 complete offline dependency resolution and parse; the lower line also passes 73 deterministic Agent/eval/lifecycle tests.

## Agent lifecycle CLI eagerly read unrelated subcommand arguments

- Root cause: the Agent handler constructed grant, promote, and rollback argument dictionaries together, so `agent grant` attempted to read nonexistent `from_alias` and `to_alias` attributes before selecting the grant macro.
- Fix summary: lifecycle macro arguments are now constructed only inside the selected subcommand branch.
- Verification: a parser/handler regression invokes `agent grant` without promote or rollback options, and the full package suite passes.

## Legacy accepted baselines used physical eval Agent identities

- Root cause: the schema-v2 migration initially required the legacy `agent` field to equal the logical dbt exposure name, but historical accepted artifacts identify the exact physical native-eval Agent object.
- Fix summary: migration accepts only the current plan's exact logical name, physical object name, or fully qualified physical Agent name; near matches still fail closed.
- Verification: focused migration tests cover both exact physical identities and reject a suffixed near match.

## REQ-007: v0.3.0 documentation overstated and omitted shipped behavior

- Root cause: adopter docs implied init could bootstrap resources, omitted Snow CLI and native-eval deployment prerequisites, described skill upload as separate from canonical CLI deploy, and did not distinguish captured CLI output and safety gates from direct macro behavior; the integration fixture also documented a passing doctor path while checking in an empty database allowlist.
- Fix summary: docs were corrected for the v0.3.0 release boundaries, artifact paths, and troubleshooting order, and the fixture explicitly allowlists only its documented sandbox database. This is historical verification superseded by the active v0.3.1 docs.
- Verification: parser-backed docs tests assert scaffolding, skill-upload, native-eval, output, artifact-path, troubleshooting, and fixture-allowlist contracts.

## REQ-011: starter scaffolding could partially overwrite adopter projects

- Root cause: the integration fixture was not package data and the existing init writer applied each configuration edit immediately, so directly adding fixture copies would not provide all-collision-before-write safety or installed-wheel availability.
- Fix summary: the fixed Orders fixture is bundled as package data and init builds a complete action/write plan, rejects every differing destination before applying any write, preserves existing semantic-view dependencies, and treats identical files as no-ops.
- Verification: focused init/CLI tests cover exact paths, preview/apply JSON, determinism, idempotency, `.dbtignore`, dependency preservation, and a late collision that leaves all earlier planned paths untouched; wheel inventory and installed-wheel smoke cover package data.

## REQ-011: Agent render hid specifications and deploy was canonical-only

- Root cause: the CLI hard-coded canonical projection, discarded successful dbt macro stdout, and always planned canonical skill uploads, so operators could not inspect or deploy the native-eval projection through the guarded CLI path.
- Fix summary: render/deploy accept only canonical or native-eval, dbt emits one marked authoritative render envelope, Python fails closed while parsing it and saves a contained deterministic spec artifact, and native-eval deploy skips only skill planning/upload while preserving all mutation gates.
- Verification: focused parser, marker, artifact, macro-contract, canonical compatibility, native-eval orchestration, and apply-preflight tests plus full package/dbt/build checks run without Snowflake calls.

## REQ-011: additive render envelope shadowed legacy raw-spec output

- Root cause: the new marked render envelope was the first dbt output line containing the specification, so existing consumers that selected the historical raw `{"models": ...}` line parsed the envelope instead of the spec.
- Fix summary: `cortex_agent__render_spec` preserves the v0.3.0 raw spec log before emitting exactly one additive marked envelope; new CLI parsing remains marker-specific.
- Verification: package marker contracts and the downstream framework's four canonical/native-eval golden comparisons cover both output consumers.

## REQ-011: runtime smoke was coupled to skill declarations

- Root cause: the only public smoke command discovered stage-backed skills and generated skill-specific questions, so an operator could not preview or invoke a general manifest-owned Agent with an arbitrary question.
- Fix summary: additive `agent smoke` resolves one logical Agent, defaults to canonical manifest-owned physical identity, uses dbt's offline render authority for explicit native-eval identity, previews without invocation, and reuses the existing bounded SSE client only after explicit connection, database/schema, manifest-match, and CLI allowlist gates; optional expected-tool checks use exact tool names.
- Verification: focused parser/CLI/invocation tests cover projection defaults/rejection, dbt-owned native-eval identity, required and blank inputs, physical overrides, preview non-invocation and null fields, apply gate ordering, endpoint forwarding, exact tool assertions, structured success, and controlled exit 2 failures while existing skill smoke remains unchanged.

## REQ-012: eval authoring undertriggered and local-write approval was underspecified

- Root cause: the deterministic frontmatter trigger list named adoption, migration, project, and Orders intents but omitted the independent dbt evaluation-authoring route; Stop 1 also lacked the exact boundary-packet and one-scope resume language required of every approval boundary.
- Fix summary: the trigger contract now includes manifest-owned dbt Agent evaluation authoring, and the local-write stop presents objective, paths, changes, commands, proof, risks, and a single approved-plan resume condition that resets on any scope change.
- Verification: project-skill tests cover expanded positive/near-miss/negative prompts, all fenced shell commands, four exact approval packets/resume conditions, and deterministic transcript routes for Orders, semantic-view adoption, Agent migration, and eval authoring.

## REQ-012: immutable SHA package pins failed doctor version alignment

- Root cause: doctor compared every dependency revision string directly to the semantic CLI version, so a full immutable Git SHA failed even when dbt installed package version 0.3.1 from that exact commit.
- Fix summary: full 40-character Git SHAs defer semantic alignment only to actual installed consumer dbt package metadata; package source-root metadata is not accepted as installation evidence, and semantic version pins continue to require an exact direct match.
- Verification: doctor tests cover a matching installed dbt package, missing installed metadata, a branch revision, mismatched installed metadata, and matching/mismatched semantic revisions.

## REQ-013: Agent lifecycle created evaluation-specific physical projections

- Root cause: public Agent lifecycle APIs accepted canonical/native-eval projections, target naming appended a configurable `_EVAL` suffix, and native-eval deployment filtered the specification while bypassing skill upload and validation.
- Fix summary: Agent render, deploy, smoke, grant, version, and alias paths now resolve one target FQN and always use the full specification; stable render artifacts use `spec.json`, while skills, MCP attachment, guards, and lifecycle semantics remain intact.
- Verification: focused deploy/CLI/macro tests assert removed interfaces, one physical identity, stable artifacts, full skill orchestration, and fixed eval compatibility targeting; offline dbt parse confirms macro compilation without Snowflake mutation.

## REQ-013: Evaluation evidence retained projection identity and accepted `_EVAL` history

- Root cause: eval metadata, the signed plan, Python `EvalPlan`, candidates, baselines, and native result metadata retained projection fields after Agent lifecycle converged on one physical object; legacy migration also accepted the plan's former physical eval identity.
- Fix summary: optional eval metadata now resolves the normal Agent FQN directly, signed plans and schema-v2 artifacts omit projection, applied runs prove Agent existence/DEFAULT before upload and fail on version drift, and `_EVAL` baseline identity is rejected as historical-only evidence.
- Verification: focused eval/baseline/CLI/macro/schema/docs tests plus credential-free integration dbt parse; no Agent lifecycle macro, Snowflake mutation, paid evaluation, consumer edit, commit, or push.

## REQ-013: Full-spec tool presence was mistaken for native evaluation coverage

- Root cause: eval validation accepted every rendered tool name, while obsolete `evaluation_supported` metadata implied deploy-time filtering; this let expected-tool metadata overstate native coverage for skills, MCP, code execution, and other capability tools.
- Fix summary: deployment always renders the full Agent independently of evaluation metadata; native `expected_tools` now resolve only to declared Analyst, Cortex Search, `web_search`, or generic custom tools, and general capability evidence preserves the five REQ-013 proof classifications without promoting attachment to invocation.
- Verification: focused macro contracts cover supported custom/Search/web/Analyst names, fail-closed unsupported capability claims, evidence classifications, removed starter metadata, and render independence; focused eval/render tests and offline dbt parse run without consumer or Snowflake changes.

## REQ-013: Active adoption guidance retained the superseded projection model

- Root cause: starter naming, the project-local skill, and adopter/reference docs still taught canonical/native-eval deployment, `_EVAL` prerequisites, and projection-specific commands after lifecycle and evaluation code converged on one physical Agent.
- Fix summary: the Orders suite model is optional and unsuffixed, guided/manual paths operate one Agent, active docs describe Agent-only and Agent-plus-eval adoption, and unpublished 0.3.1 install guidance uses a reviewed local checkout.
- Verification: docs/project-skill/starter/init/CLI contracts, offline dbt parse, package build/Twine/wheel inventory, full tests where feasible, and hooks; historical references remain only as explicitly superseded evidence.

## REQ-014: Installed-wheel smoke did not prove the adopter lifecycle

- Root cause: distribution CI installed the wheel and checked help/version plus an init preview, but never resolved a consumer dbt package or exercised doctor, manifest, render, deploy preview, smoke preview, or optional eval planning from the installed CLI.
- Fix summary: a deterministic external-workspace verifier now installs the exact wheel, constructs isolated Agent-only and Agent-plus-eval projects, executes the complete credential-free preview sequence, and asserts one unchanged physical Agent identity with no eval lifecycle action.
- Verification: script unit tests, static package/release workflow contracts, both supported dbt lines in package CI, local installed-wheel execution, full tests, build/Twine/inventory, YAML parsing, and patch hygiene run without Snowflake or paid actions.

## REQ-013/014: Empty Agent proof and verifier command safety gaps

- Root cause: evaluation treated an empty `DESCRIBE AGENT` result as an Agent with no DEFAULT, while the installed-wheel command guard allowed any command containing `init` to carry `--apply`; package CI cleanup also used folded YAML that joined two cleanup commands incorrectly.
- Fix summary: empty Agent descriptions now fail explicitly before stage upload or START, installed-wheel `--apply` is restricted to the exact `dbt-cortex-agent init` command and direct Snow CLI execution is rejected, and CI cleanup is one valid residue-removal command.
- Verification: focused eval and installed-wheel safety tests cover empty descriptions, non-CLI `init --apply`, direct `snow`, and mutation-command rejection; workflow YAML parsing and the full verification matrix cover the corrected cleanup step.

## REQ-008/014: Tracked-secret scan rejected a synthetic immutable Git SHA

- Root cause: the immutable-SHA doctor regression asserted a realistic 40-character hexadecimal commit fixture without the scanner's line-scoped test-data annotation, so `detect-secrets==1.5.0` classified the assertion at `tests/test_doctor.py:161` as a high-entropy secret.
- Fix summary: the synthetic SHA now has one line-scoped `pragma: allowlist secret` annotation at its test-fixture constant and every test reuses that constant; no detector, file, or path exclusion was added. Single-Agent release notes were also moved from `Unreleased` into the dated 0.3.1 section, and REQ-011 is indexed as historical projection evidence superseded by REQ-013.
- Verification: `tests/test_ci.py::test_synthetic_immutable_sha_is_narrowly_allowlisted`, documentation contracts, and the exact repository-root tracked non-lock-file scan pin the exception and require zero findings.

## REQ-007/008: Repository checks depended on the caller working directory

- Root cause: the tracked-file scan produced package-relative names with `git ls-files` but opened them from the caller working directory, while the documentation test compared an absolute test path with relative discovered paths. Running either command from another checkout could scan unrelated same-named files or include `test_docs.py` in its own forbidden-text corpus.
- Fix summary: the workflow scan opens tracked paths from `GITHUB_WORKSPACE`, and the documentation test compares resolved paths. No secret detector, baseline, file, or path exclusion was added.
- Verification: CI contract coverage pins the workspace anchor; the exact scan and absolute-path documentation test run from an external directory, followed by the full package suite.

## REQ-005: Installed-package eval preview used an ambiguous unqualified macro

- Root cause: the CLI invoked `cortex_eval__execution_plan` without the owning package namespace, leaving run-operation resolution dependent on the consumer project's macro namespace and dbt package dispatch behavior.
- Fix summary: the CLI now invokes `dbt_cortex_agent.cortex_eval__execution_plan`; the public unqualified macro remains available for direct dbt usage.
- Verification: focused command construction and an installed-package consumer regression under dbt Core 1.12 prove the package-qualified run-operation renders the read-only plan. Existing dbt `>=1.10,<2.0` support documentation is unchanged.

## REQ-029: Public dbt evaluation macro referenced undefined legacy helpers

- Root cause: source-text tests asserted selected macro names but never resolved every Cortex macro call against the installed definition set. Unreachable exposure-era branches retained `cortex_agent__build_spec`, while result metadata called the removed `cortex_agent__current_spec_hash`; macro run names were also concatenated into SQL without the Python path's validator.
- Fix summary: remove the unreachable non-model branches, remove unsupported `spec_md5` result metadata, validate run names to letters/digits/underscores at every macro entry, and recursively check all package macro calls against definitions.
- Verification: `tests/test_eval_plan_macros.py`, offline integration `dbt parse`, installed-wheel verification, and the full package suite.

## REQ-030: Runtime assertion and programming failures lost their true evidence class

- Root cause: expected-tool failure raised after a paid response but before CLI payload emission, raw-event collisions were checked after invocation, and broad lifecycle catches converted programming defects into controlled partial failures.
- Fix summary: emit the normalized failed smoke payload while preserving exit `2`, preflight raw-event destinations, and re-raise exceptions outside the controlled operational error set. Keep multi-database resource allowlists independent of the connection-default database.
- Verification: `tests/test_agent_commands.py`, `tests/test_lifecycle.py`, `tests/test_deployment.py`, branch coverage, mutation tests, and the full package suite.