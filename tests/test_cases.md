# Test cases

## Final Review: HTTP Resources And Proof Isolation

- REQ-030 final-review criteria: behavioral tests in `tests/test_invoke.py` raise real stdlib `HTTPError` with synthetic owned bodies, inject body/cursor/connection close failures and artifact-write failure, and assert primary identity, cleanup order, secondary metadata, and bounded evidence. Existing partial-stream tests remain required.
- REQ-028 final-review criteria: `tests/test_live_multi_database_verifier.py` exercises absent, empty, and conflicting inherited `DBT_EXECUTABLE` values across preview, applied fake proof, lifecycle/retirement and separate cleanup-only. The isolated binary must match the direct dbt command; missing local venvs do not authorize a host fallback. No real install or live proof is implied.
- REQ-021 typing: explicitly check `src/dbt_cortex_agent/dbt_runner.py` with mypy in addition to the configured module set; existing command-runner callers retain kwargs and environment behavior.

## Independent-Review Blockers: Local Behavioral Evidence

- `TC-022-06`/`TC-022-07`/`TC-022-09`: `tests/test_eval.py::test_source_rebuild_cannot_exclude_originally_in_scope_failure` covers both tool metrics and START/STATUS/fetch/fetch-retry rebuilds with unchanged input/ref and changed test_type; original failures remain counted and candidates cannot gate or become baselines.
- `test_source_drift_blocks_start_without_rebinding`, `test_source_drift_after_failed_run_stops_transient_retry`, and `test_source_count_drift_fails_validation_before_upload_or_start` cover validation/upload/retry drift, no rebind onto a changed source, and pre-effect cardinality failure.
- `test_snapshot_rejects_invalid_mapping`, `test_snapshot_is_immutable_order_independent_and_requires_known_result_input`, and `test_invalid_source_after_start_retains_original_binding_and_fails` cover complete, immutable mappings, duplicates/missing values, changed input, and indeterminate evidence after invalid rebuilds.
- `test_candidate_snapshot_binding_rejects_inconsistent_evidence` binds persisted input/ref/type and drift evidence while preserving mapping metadata in compact baselines; `test_legacy_candidate_without_snapshot_keeps_existing_validation` explicitly pins the older-v2 provenance limitation. Existing boundary and partial-result tests remain required. No transactional freeze or live ingestion proof is claimed.
- `TC-032-01`/`TC-032-05`: `tests/test_deployment.py::test_apply_expected_identity_reaches_materialization_before_effects` runs Python apply through actual Jinja with FQN drift, unexpected model IDs and matching identity; no hook, stage inspection or Agent DDL occurs on rejection.
- `TC-032-01`: `tests/test_materialization.py::test_supplied_invalid_identity_map_cannot_disable_guard` rejects null, non-mapping, empty and missing-FQN expectations; existing no-map direct-build cases remain valid.
- `TC-022-01`: `tests/test_deployment.py::test_unselected_agent_ancestor_rejected_before_skill_planning` covers direct/indirect and metadata-disabled ancestors through parent_map and depends_on. `test_explicit_agent_ancestor_includes_skills_and_resource_databases` verifies explicit selection includes skill uploads and all resource databases.
- `TC-023-07`/`TC-023-08`: `test_absent_agent_creates_one_version_and_retry_reuses_it`, `test_post_create_interruption_requires_recovery_without_duplicate`, `test_unknown_creation_inspection_fails_before_mutation`, `test_initial_version_metadata_acknowledgement_loss_retries_without_commit`, `test_post_create_managed_metadata_allows_safe_retry`, and `test_external_unmanaged_agent_adoption_remains_supported` in `tests/test_deployment.py` exercise persistent simulated native state and actual Jinja. Initial CREATE without managed metadata requires explicit recovery, not automatic convergence; external adoption and marked-version retries retain their prior behavior.
- These are offline behavioral checks, not native specification-equivalence, historical stage-content, concurrency, current-wheel or live Snowflake proof.

## Task 7: Local Product And Release Evidence

- `TC-028-07` and `TC-028-09`: documentation contracts reject missing grant-macro invocation, role-switch promises, and offline compile claims; all canonical target arguments use sandbox.
- `TC-022-11` and `TC-026-10`: `tests/test_live_multi_database_verifier.py` exercises both-database retention, failed proof, failed cleanup, combined failure, cleanup-only updates, and missing/mismatched prior proof. These are synthetic behavior tests, not live qualification.
- `TC-032-01` and `TC-028-08`: `tests/test_installed_wheel_verifier.py` parses a temporary consumer with locally installed dbt's default schema generation, then executes materialization against that manifest through the existing Jinja harness, and rejects full-FQN drift in consumer evidence. The installed-wheel harness adds resolved-schema/deploy assertions, but its clean-install matrix remains pending.
- Existing evidence-map schema/version, historical reports, and pending-live classifications remain unchanged in meaning. Test collection is linkage, not execution evidence.

## Task 6: Proof Linkage Contract

`tests/requirement_evidence.json` is the machine-readable inventory for every
numbered acceptance criterion in REQ-021 through REQ-032 and every canonical
developer-guide section. `TC-*` IDs below describe intended tests, not completion.
Legacy source comments are not evidence. Each map entry contains a bounded claim,
proof references and gaps. Empty gaps mean only the linked local scope is covered,
not live/release qualification. `behavioral` means code executed with local/fake
boundaries; `structural` means source/schema/syntax checks. `live_historic` points
to an existing report, not a current retained run artifact; `live_pending` means
no new live proof. Collection checks links but does not execute linked tests.

Task 6 extends `TC-028-10` with the following concrete contract tests:

- `tests/test_requirements_contract.py::test_evidence_map_schema_and_complete_criterion_inventory`: exact criterion coverage, proof kinds, references and explicit gaps.
- `tests/test_requirements_contract.py::test_offline_proofs_link_to_collected_test_nodes`: resolve concrete functions/parameter cases using current-session pytest collectors, including focused runs; no recursive pytest.
- `tests/test_requirements_contract.py::test_nonexistent_or_comment_only_linkage_is_rejected` and `test_comment_only_module_collects_no_evidence`: reject fake IDs and comment-only source.
- `tests/test_requirements_contract.py::test_article_claims_link_to_requirements_and_bounded_proofs`: guide-section/criterion coverage, not semantic completeness of every prose sentence.
- `tests/test_requirements_contract.py::test_fixture_schemas_and_proof_links`: declared compatibility/SSE fixture contracts and provenance, with malformed-schema negatives.
- `tests/test_requirements_contract.py::test_incomplete_requirement_statuses_do_not_claim_complete`: keep open gaps visible in requirements and index.

## Task 5: REQ-030 and REQ-031 hardening

- REQ-030 supplement criterion 1: `tests/test_invoke.py::test_runtime_partial_evidence_survives_stream_failure`, `test_runtime_limits_are_incremental_with_partial_evidence`, `test_unframed_stream_is_bounded_before_json_decode`, and `test_truncated_http_read_preserves_accepted_events` exercise real framing/normalization and local JSONL writes.
- REQ-030 criterion 2: `test_runtime_deadline_includes_setup_and_slow_stream`, `test_setup_overrun_closes_connection_without_opening_http`, `test_runtime_eof_read_checks_deadline_after_blocking`, and `test_invalid_runtime_budget_fails_before_acquisition` use a fake monotonic clock and bounded fake transport; no hard-deadline proof is claimed.
- REQ-030 criterion 3: `test_runtime_acquisition_and_independent_cleanup`, `test_runtime_programming_defect_propagates_despite_cleanup`, and `test_raw_write_failure_cannot_mask_stream_failure` exercise acquisition, response/cursor/connection close, primary identity, and evidence-write failures.
- REQ-030 criterion 4: `tests/test_agent_commands.py::test_smoke_runtime_error_retains_partial_response_and_real_artifact` verifies human/JSON partial evidence and exit 2; raw opt-in and collision tests exercise the real invoker.
- REQ-031 criterion 1: `tests/test_eval_verify.py::test_later_suite_failure_preserves_completed_suite_result` includes a connector-module exception after successful work; `test_unexpected_programming_error_is_not_mislabeled_as_infrastructure` covers AssertionError, TypeError, and AttributeError.
- REQ-031 criterion 2: `test_post_candidate_failure_retains_execution_evidence` and `test_later_baseline_error_retains_both_candidate_paths_and_prior_gate` verify distinct execution/gate states, retained paths/prior results, and unattempted suites.
- REQ-031 criterion 3: `test_verify_binds_current_plan_even_for_self_consistent_candidate`, `test_verify_rejects_consistent_foreign_candidate_fields`, `test_verify_gates_exact_loaded_candidate_without_reopening`, and `test_current_plan_identity_drift_blocks_paid_run_even_with_same_signature` bind real loaded candidate evidence without a second file read.
- REQ-031 criterion 4: `test_evaluation_acquisition_cleanup_preserves_primary` and `tests/test_eval.py::test_evaluation_cleanup_only_failure_closes_both_and_preserves_written_candidate` cover connector acquisition, independent closes, primary defects, and durable file retention after cleanup-only failure.

All task 5 evidence is local and synthetic, not live connector/dbt/Snowflake qualification.

## REQ-032: Resolved mutation identity

1. `TC-032-01`: `tests/test_materialization.py::test_materialization_uses_resolved_identity` executes the materialization with raw config different from the resolved relation.
2. `TC-032-02`: `tests/test_lifecycle.py::test_route_and_drop_delegate_to_dbt_macros` checks expected-FQN arguments; `test_route_rejects_inspected_identity_mismatch` proves no mutating command occurs.
3. `TC-032-03`: `tests/test_identity_macros.py` executes route/drop macros with matching, missing, and mismatched expectations and checks the recorded effects.
4. `TC-032-04`: `tests/test_fresh_manifest.py` exercises custom output locations, precedence, preserved profile environments, stale output, and parse failures using a fake dbt process.
5. `TC-032-05`: Targeted offline pytest runs the above behavior tests and adjacent contracts without remote operations.

## REQ-021: Python design and maintainability

1. `TC-021-01`: Reject malformed external payload shapes before domain access.
2. `TC-021-02`: Property-test immutable identity, path, context, and policy values.
3. `TC-021-03`: Enforce command/domain separation and intentional public exports.
4. `TC-021-04`: Verify categorized controlled errors for expected failures.
5. `TC-021-05`: Verify finite configurable subprocess and network bounds.
6. `TC-021-06`: Import documented public APIs from an installed wheel.
7. `TC-021-07`: Collect every tracked test by default and use explicit markers.
8. `TC-021-08`: Enforce lint, typing, branch coverage, complexity, dependency, inventory, and secret gates.
9. `TC-021-09`: Run targeted property and mutation tests for safety boundaries.
10. `TC-021-10`: Snapshot supported `0.0.5` CLI, JSON, artifact, and macro behavior.

## REQ-022: Package-native workflow safety

1. `TC-022-01`: Prove complete target/resource authorization precedes deploy effects.
2. `TC-022-02`: Prove previews perform no connection, write, mutation, runtime, or spend.
3. `TC-022-03`: Prove one explicit execution context reaches every child client.
4. `TC-022-04`: Prove supported authentication end to end and reject unsupported combinations early.
5. `TC-022-05`: Inject failure after each deploy phase and retain completed-phase evidence.
6. `TC-022-06`: Prove eval resource/policy validation precedes build and paid work.
7. `TC-022-07`: Reject non-finite, malformed, and incomplete eval policy/results.
8. `TC-022-08`: Prove eval does not opportunistically provision shared infrastructure.
9. `TC-022-09`: Preserve completed suite results across later suite failure.
10. `TC-022-10`: Refuse evidence collisions and path escape.
11. `TC-022-11`: Run public deploy/verify commands from the exact protected wheel.
12. `TC-022-12`: Verify adopter code contains policy but no duplicate workflow sequencer.

Task 2 supplement to `TC-022-06`, `TC-022-07`, and `TC-022-09`:

- `tests/test_eval.py::test_ineligible_candidates_cannot_compare_gate_or_be_accepted` executes comparison, file-backed gate, and acceptance with drift, failed/non-completed status, and non-boolean pass flags.
- `test_compare_and_gate_reject_invalid_evidence` and `test_native_run_rejects_invalid_observations_without_candidate` cover null, nonfinite, duplicate, missing, and malformed row/count evidence through real artifact and mocked native-run paths.
- `test_boundary_exclusions_preserve_completeness_and_observation_grain`, `test_native_fetch_annotates_boundaries_before_completeness`, and `test_boundary_exclusion_cannot_hide_invalid_observations` cover native IDs varying by metric, source annotation, absent/null/nonfinite exclusions, duplicate excluded rows, and mandatory boundary answer scores.
- `test_unknown_signed_policy_fails_plan_and_pre_connector_apply` and `tests/test_eval_verify.py::test_verify_rejects_unknown_policy_in_later_suite_before_effects` prove unknown keys fail before any connector/build/evaluation.
- `tests/test_eval_verify.py::test_verify_real_candidate_gate_never_greens_invalid_evidence` and `test_verify_honors_excluded_tool_observations` execute real compare/gate/validation through verify, with and without an established baseline.
- `test_entirely_excluded_tool_cannot_satisfy_policy` and `test_ineligible_baseline_never_authorizes_comparison` preserve explicit policy and baseline eligibility.

All task 2 evidence is local and synthetic; no new live qualification is claimed.

Task 4 supplement to `TC-022-02`, `TC-022-03`, and `TC-022-05`:

- `tests/test_skills.py::test_yaml_is_comparison_evidence_not_upload_authority` and `test_parse_only_metadata_discovers_jinja_declared_skills` cover raw/compiled YAML/JSON, metadata-only parse, and both node metadata representations.
- `test_model_metadata_mismatch_fails_before_local_file_check`, `test_unresolved_or_malformed_metadata_is_not_an_empty_plan`, `test_detectable_unresolved_body_cannot_silently_plan_empty`, and `test_legacy_capabilities_location_fails_actionably` pin fail-closed discovery before effects.
- `test_later_copy_preserves_each_destination_and_stops` exercises failed exit, OSError, and timeout after a successful destination using the real upload function.
- `test_cli_later_copy_retains_outcomes_and_role_override` runs both public CLI paths with mocked subprocesses, actual connection-context resolution, human/JSON outputs, different connection/approved roles, and no later copy/build.
- `test_skill_smoke_passes_role_through_command_and_runtime` exercises the command and smoke function together; existing `tests/test_invoke.py::test_direct_invocation_sends_explicit_runtime_role` pins the HTTP header boundary.

This is offline synthetic behavior evidence, not live dbt/Snowflake qualification.

## REQ-023: Macro API and reconciliation

1. `TC-023-01`: Invoke every public macro from an installed consumer.
2. `TC-023-02`: Enforce focused macro ownership boundaries.
3. `TC-023-03`: Fuzz SQL-bearing external values and reject unsafe serialization.
4. `TC-023-04`: Verify materialization never changes session role.
5. `TC-023-05`: Verify docs/output never claim hooks or adapter commit roll back Agent DDL.
6. `TC-023-06`: Exercise complete Agent state inspection fixtures.
7. `TC-023-07`: Prove changed content creates one version and unchanged content creates none independently of DEFAULT.
8. `TC-023-08`: Inject each durable-phase failure and prove retry convergence.
9. `TC-023-09`: Verify independent routing, metadata, MCP, grant, and LIVE postconditions.
10. `TC-023-10`: Verify signed eval identity, refs, policy, and pre-START provenance.
11. `TC-023-11`: Reject result-table and normalized-run collisions.
12. `TC-023-12`: Verify legacy macros and fictional API docs are absent.

Task 3 supplement to `TC-023-04`, `TC-023-07`, `TC-023-08`, `TC-023-09`,
`TC-022-05`, and `TC-026-05`/`TC-026-06`/`TC-026-09`:

- `tests/test_deployment.py::test_managed_no_change_repairs_live_without_commit_or_default` executes real Jinja inspection/reconciliation with existing or missing LIVE, optionally reconciling the alias while DEFAULT remains older.
- `test_durable_deploy_failure_retry_converges` injects metadata, alias-unset/set, LIVE-add, inspection, and postcondition failures after commit; retries preserve exactly one new version.
- `test_no_change_live_failure_retry_verifies_without_commit` fails LIVE repair/verification with already-managed content and proves retry convergence without any COMMIT.
- `test_multi_agent_durable_outcomes_survive_failure_and_retry` drives Python deploy through real Jinja for two same-named Agents in different databases, duplicates output across stdout/stderr, and retains independent phases after one Agent fails.
- `test_deploy_programming_error_after_commit_propagates` verifies AssertionError, TypeError, and AttributeError remain visible after a durable commit.
- `tests/test_identity_macros.py::test_retirement_failure_evidence_and_retry` drives Python retirement through the existing Jinja harness: rejected DROP, lost acknowledgement after effect, failed inspection, and conflicting postconditions for existing/absent Agents.
- `test_retirement_programming_errors_propagate` exercises programming defects during DROP and post-drop inspection without conversion to controlled failure.
- `tests/test_lifecycle.py::test_retirement_without_acknowledgement_reports_unknown` and `test_retirement_preserves_completion_if_later_evidence_is_malformed` pin unknown versus acknowledged completion without inventing post-state.
- `tests/test_agent_commands.py::test_drop_partial_failure_retains_evidence_and_exits_two` checks command output/exit while keeping retained dependencies explicit.

This supplement is local simulated behavior evidence, not new live qualification.

## REQ-024: Agent scaffold and developer journey

1. `TC-024-01`: Preview deterministic bare-Agent paths without a Semantic View or connection.
2. `TC-024-02`: Add optional Analyst dependency and prove dbt rejects missing, duplicate, or non-Semantic-View models before deployment.
3. `TC-024-03`: Add optional eval files targeting the same logical Agent.
4. `TC-024-04`: Verify generated content contains no invented business/environment semantics.
5. `TC-024-05`: Preserve arbitrary experimental mappings without dedicated private-preview CLI flags.
6. `TC-024-06`: Round-trip `EnableCortexSense` and `FallbackWarehouse` as opaque configuration.
7. `TC-024-07`: Prove all-or-nothing collision validation, identical no-op, and differing failure.
8. `TC-024-08`: Prove preview writes nothing and apply emits stable path actions.
9. `TC-024-09`: Parse and compile installed bare, Analyst, and experimental fixtures.
10. `TC-024-10`: Verify docs and project skill teach the same generic workflow.

## REQ-025: Version promotion, rollback, and recovery

1. `TC-025-01`: Inventory ordered versions, aliases, DEFAULT, LAST, and LIVE read-only.
2. `TC-025-02`: Validate offline routing syntax/policy without connection, then validate target existence before applied mutation.
3. `TC-025-03`: Scan Python for Agent DDL and prove dbt macro delegation.
4. `TC-025-04`: Verify alias-only routing leaves DEFAULT unchanged.
5. `TC-025-05`: Verify explicit DEFAULT movement and postcondition.
6. `TC-025-06`: Roll back while preserving all newer committed versions.
7. `TC-025-07`: Roll forward to an existing version without committing.
8. `TC-025-08`: Smoke committed version, alias, DEFAULT, and LIVE with provenance.
9. `TC-025-09`: Bind evaluation to pre-START version and reject drift.
10. `TC-025-10`: Prove deploy content idempotency while DEFAULT points backward.
11. `TC-025-11`: Inject failure between alias/default movement and prove retry convergence.
12. `TC-025-12`: Reject missing, unsafe, unapproved, and stale routing; verify conflicting postconditions fail and retry converges across the non-transactional alias gap.
13. `TC-025-13`: Live-prove distinct V1/V2 promotion, rollback, roll-forward, and routed invocation.
14. `TC-025-14`: Prove final unchanged deployment creates no V3 or routing churn.

## REQ-026: Guarded Agent retirement

1. `TC-026-01`: Preview exactly one manifest-owned physical Agent.
2. `TC-026-02`: Require apply, explicit connection, allowlists, and exact FQN confirmation.
3. `TC-026-03`: Preview retained dependency classes offline and inventory Agent state before applied drop.
4. `TC-026-04`: Prove only a validated dbt macro emits `DROP AGENT`.
5. `TC-026-05`: Verify post-drop absence before success.
6. `TC-026-06`: Distinguish idempotent already-absent from newly dropped.
7. `TC-026-07`: Prove dbt graph removal never triggers Agent deletion.
8. `TC-026-08`: Prove dependent objects, files, and evidence are retained.
9. `TC-026-09`: Verify stable controlled partial and failure output.
10. `TC-026-10`: Use guarded public retirement in bounded live-proof cleanup.

## REQ-027: Runtime protocol and compact output

1. `TC-027-01`: Unit-test independent framing, normalization, accumulation, and rendering.
2. `TC-027-02`: Parse multiline, boundary, and DONE streams and reject unterminated streams.
3. `TC-027-03`: Categorize malformed JSON, Agent, HTTP, and timeout errors.
4. `TC-027-04`: Normalize answer, tools, SQL, bounded tables, charts, annotations, metadata, errors, duration, and version.
5. `TC-027-05`: Snapshot concise answer-first human output.
6. `TC-027-06`: Snapshot normalized bounded JSON without raw events.
7. `TC-027-07`: Verify explicit bounded collision-safe raw artifact handling.
8. `TC-027-08`: Prove exact tool evidence with no inference from status or attachment.
9. `TC-027-09`: Replay recorded protocol fixtures including unknown additive events.
10. `TC-027-10`: Verify base dependencies exclude pandas and async HTTP and future async reuses normalization.

## REQ-028: Executable developer and CI/CD guide

1. `TC-028-01`: Verify architecture and matching `0.0.9` candidate install coordinates, dated candidate status, aligned CI version assertion, and narrow requirements exceptions including REQ-032; preserve historical release evidence.
2. `TC-028-02`: Verify generic-first creation and optional capability examples.
3. `TC-028-03`: Parse validation, deploy, smoke, and recovery command sequence.
4. `TC-028-04`: Parse evaluation, gate, and baseline command sequence and approval labels.
5. `TC-028-05`: Parse versions, promote, rollback, roll-forward, and drop sequence.
6. `TC-028-06`: Verify PR, protected-main, and release examples retain policy-only adopter ownership.
7. `TC-028-07`: Verify authentication, RBAC, allowlist, cost, partial-state, and evidence guidance.
8. `TC-028-08`: Run core guide journeys in an installed-consumer fixture.
9. `TC-028-09`: Cross-check README, references, skills, adopter docs, and release identity.
10. `TC-028-10`: Validate claim-to-requirement-to-proof evidence map and sanitization.

## REQ-029: Macro evaluation execution safety

1. `TC-029-01`: Verify every package-qualified Cortex macro call resolves to a definition.
2. `TC-029-02`: Reject evaluation run names outside letters, digits, and underscores before SQL interpolation.
3. `TC-029-03`: Remove unreachable legacy Agent branches and undefined specification helpers.

## REQ-030: Runtime failure evidence

1. `TC-030-01`: Preserve normalized response evidence and exit `2` on expected-tool mismatch.
2. `TC-030-02`: Reject an existing raw-event destination before Agent invocation.
3. `TC-030-03`: Propagate programming defects instead of reporting controlled partial failure.
4. `TC-030-04`: Authorize all manifest-resolved resource databases independently of connection-default database context.

## REQ-031: Shared controlled failure contract

1. `TC-031-01`: Classify the bounded standard operational exception set through the shared contract.
2. `TC-031-02`: Classify Snowflake connector exceptions without requiring the optional connector in the base package.
3. `TC-031-03`: Reject programming defects from controlled-operation classification.
4. `TC-031-04`: Verify evaluation uses the shared exception tuple and propagates programming defects.
5. `TC-031-05`: Verify shared routing state inspection preserves controlled evidence and propagates programming defects.

## REQ-016: Agent monitor access contract

1. Verify `access.usage_roles` renders `GRANT USAGE ON AGENT` and `access.monitor_roles` renders `GRANT MONITOR ON AGENT` through the same sandbox-guarded macro.
2. Verify the starter demonstrates an evaluation/monitor role under both lists while keeping a separate runtime-only role.
3. Verify access metadata does not leak into rendered Agent specifications and unrelated privileges remain consumer-owned.

## REQ-017: Tool dependency access contract

1. Verify Cortex Search tools accept only a strict three-part `search_service` identifier.
2. Verify `tools[].access.usage_roles` is a list of safe role identifiers.
3. Verify the sandbox-guarded Agent grant lifecycle renders/applies `USAGE` on exactly the declared Cortex Search Service and does not create broad schema or future grants.

## REQ-002: v0.3.0 identity and Python ownership

1. Verify the historical v0.3.0 identity and ownership boundary remains the foundation of the current package while active release surfaces identify v0.3.1.
2. Verify Python deploy and lifecycle commands invoke the public dbt Agent macros with the expected arguments.
3. Scan Python source and fail if mutating `CREATE AGENT`, `ALTER AGENT`, or `DROP AGENT` DDL appears.
4. Verify the CLI imports internal eval modules successfully while `dbt_cortex_agent.eval` exposes no lifecycle convenience API.

## REQ-003: Explicit bootstrap configuration

1. Verify init fails without a package source when no known dependency exists, but leaves exact existing Git, package-coordinate, and local declarations unchanged.
2. Verify an arbitrary Git fork is not identified by repository suffix alone and an explicitly requested source is matched exactly.
3. Verify the default revision is computed from the installed Python package version.
4. Verify deployment vars require an explicit target and adopter-provided database allowlist, include repeatable allowed targets/databases, and automatically include only the explicit target.
5. Verify Agent and eval schema vars are added only through explicit schema options.
6. Verify preview writes nothing, apply appends only missing package/vars, and comments, unrelated fields, and existing values remain byte-preserved.
7. Verify doctor reports actionable missing-target and incomplete-allowlist diagnostics without suggesting an implicit target.

## REQ-004: Lifecycle and safety hardening

1. Verify eval discovery excludes absent, empty, non-mapping, and explicitly disabled metadata while exact duplicate suite selection fails closed.
2. Verify empty and unscored eval result responses retry to a bound and malformed/unterminated SSE plus HTTP hangs fail closed.
3. Verify shared unquoted identifier/FQN/stage validators reject injection, quoting, traversal, unsafe aliases/versions/roles, and invalid physical Agent names.
4. Verify candidate/baseline writes remain under configured roots and compare/gate/accept reject traversal and incompatible or malformed artifact schemas.
5. Verify every manifest-dependent CLI operation parses before loading, `--no-parse` is explicit, and parse failure prevents manifest loading and downstream calls.
6. Verify upload, mutation, and paid eval reject a configured database that differs from dbt-resolved target metadata and reject environment-only connections.
7. Verify multi-Agent skill smoke maps logical Agents independently and allows a physical override only for one selected Agent.
8. Verify unchanged deploy alias reconciliation emits an alias move to the current default and emits no COMMIT.
9. Verify package guidance contains no repository-only `make dbt-focus-*` instruction.
10. Run full Python tests, static guards, package build, and integration-consumer dbt parse using fakes for remote behavior.

## REQ-005: dbt-rendered evaluation execution plan

1. Verify the dbt plan macro reuses authoritative validation, target Agent, dataset, config, stage, target context, metrics, thresholds, tolerances, and ordered refs without remote queries.
2. Verify Python parses exactly one schema-v1 plan from the package-qualified `dbt run-operation` output after fresh parse and preserves injectable plan/command fakes, including installed-package resolution under dbt 1.12.
3. Verify malformed, duplicate, or mismatched plan identity/signature fields fail closed before evaluation.
4. Verify table validation rejects duplicate/missing refs and duplicate input queries, and result annotation uses stable unique refs.
5. Verify pre-start DEFAULT is retained as the evaluated version and post-run DEFAULT drift creates an indeterminate failed artifact.
6. Verify artifact schema v2 persists plan identity/signature, ordered refs, policy, and pre/post provenance.
7. Verify compare/gate reject suite-policy changes and always enforce baseline tolerances when candidate tolerances are wider.
8. Verify missing eval dependencies and expected CLI errors are controlled and actionable.
9. Run focused/full Python tests, package build, integration-consumer dbt parse, and macro structural/offline tests without live evaluation.
10. Verify eval run exposes shared target/database allowlists and rejects missing or mismatched allowlists before connector construction.
11. Verify the signed plan requires `target_role`, the CLI payload exposes it, and applied execution issues `USE ROLE` before warehouse/database/schema.
12. Verify known legacy accepted evidence migrates using current plan metrics, thresholds, tolerances, ordered refs, and suite signature while preserving legacy summary/run provenance.
13. Verify migration previews without writing, applies only to the requested baseline directory, rejects unknown/failed/mismatched evidence, and requires explicit force for existing targets.

## REQ-006: stable domain-oriented CLI

1. Verify the console script and all existing top-level/nested command names remain stable after dispatch moves into bootstrap, manifest, skill, Agent, and eval command modules.
2. Verify `0` success/pass, `1` diagnostic/gate failure, and `2` controlled config/runtime failure for human and JSON output modes.
3. Verify expected connector, HTTP, JSON, filesystem, permission, and baseline-overwrite failures produce no traceback.
4. Verify every mutation or paid command remains dry-run by default and help labels the explicit `--apply` boundary.
5. Verify top-level and nested help provide descriptions, option help, mutation/spend labels, and examples.
6. Verify `--json` emits machine-readable stdout for applicable bootstrap, manifest, skill, Agent, and eval results without mixed human text.
7. Verify role is absent from parser/config/environment behavior and package root exports only `__version__`.
8. Verify only the `runtime` connector extra is published and migration guidance covers former `invoke` and `eval` installs.
9. Run focused/full tests, import/static checks, package build, and clean wheel-install CLI smoke from outside the repository without live operations.

## REQ-007: complete adopter documentation

1. Verify the root README contains product identity, two current install surfaces, compatibility, non-mutating quickstart, controlled deploy, CLI-versus-macro guidance, lifecycle/eval overview, docs map, limitations, and policies.
2. Verify every shipped command and command-specific option appears in the CLI reference and mutation/runtime/spend commands are labeled from parser help.
3. Verify all documented local Markdown links resolve and adopter docs contain no copied-tooling, repository-only Make, embedded-package, or contradictory release-status language.
4. Verify package, README, installation, compatibility, CLI, and upgrade surfaces identify v0.3.1; older versions appear only in explicitly historical compatibility or release context.
5. Verify YAML exposure/eval examples parse and preserve the manifest-owned metadata locations and required fields.
6. Verify quickstart CLI examples parse through the shipped parser and contain no `--apply`, runtime smoke, baseline write, or paid evaluation execution.
7. Verify evaluation docs state that the CLI requires a materialized eval table, stage, and normally deployed Agent and does not create or deploy those prerequisites.
8. Run docs tests, the full Python suite, package build, and integration-consumer dbt parse without live mutation, runtime invocation, or paid evaluation.
9. Verify README, installation, upgrade, init, package metadata, and test fixtures use the public HTTPS repository/tag and contain no private-index, private-Git, or SSH installation wording.
10. Verify active pre-publication CLI installation uses a reviewed clean local checkout, documents the future pinned PyPI command only as a release contract, and keeps dbt as an HTTPS Git dependency because `dbt deps` does not install from PyPI.
11. Verify the docs explain that PyPI `0.3.1` and Git tag `v0.3.1` are one immutable release and that `doctor` checks CLI, declared dependency, and installed consumer dbt package alignment.

## REQ-008: standalone CI and release verification

1. Verify one active root package workflow runs on pull request, push, and manual dispatch with read-only permissions and no nested workflow files.
2. Verify workflow text contains no secret interpolation, Snowflake credential variables, private-key setup, `--apply`, live runtime smoke, baseline acceptance, or paid evaluation.
3. Verify the Python matrix exactly covers 3.10, 3.11, 3.12, and 3.13 and package metadata declares the same range.
4. Verify the dbt matrix pins lower-bound dbt-core 1.10 with dbt-snowflake 1.10.3 and authority dbt-core 1.11 with dbt-snowflake 1.11.4, consistent with `dbt_project.yml`; dbt 1.9 is excluded by integration-fixture evidence.
5. Verify policy/docs/project health, full tests, byte-compilation, dbt dependency/parse, macro determinism, single-Agent fixture preview, optional eval-plan preview, and dry-run lifecycle are required jobs or steps.
6. Verify version alignment, pyproject/dbt consistency, package inventory, generated-residue, and secret-scan guards are present and tested.
7. Build sdist and wheel, run Twine checks, inspect wheel inventory, and install the wheel into a clean environment outside the checkout.
8. Exercise installed CLI help/version and deterministic consumer fixture previews without a connection, mutation, runtime invocation, or spend.
9. Generate pinned dependency-license and CycloneDX SBOM artifacts outside the checkout.
10. Run focused/full tests and local build/install checks, then remove dbt, build, cache, license, and SBOM residue from the checkout.

## REQ-009: simple maintainer-led project policy

1. Verify `GOVERNANCE.md` and `MAINTAINERS.md` are absent and no local Markdown link references them.
2. Verify project policy surfaces contain no two-maintainer, vacant-role, employer-approval, legal-review, or publication-block language.
3. Verify CONTRIBUTING and the pull request template retain minimal Apache-2.0 authorization and attribution language without special employer approval claims.
4. Verify SECURITY retains private vulnerability reporting and SUPPORT retains best-effort community support.
5. Verify CODEOWNERS names the maintainer without comments or entries for deleted governance files.
6. Run focused docs/policy tests, the full Python suite, tracked-file secret scanning, and package build.

## REQ-010: trusted PyPI publishing

1. Parse both root workflows and verify release publishing triggers only on a published GitHub release or manual build-only dispatch, never push or pull request.
2. Verify the build job has read-only permissions and performs tag checkout, preflight, critical tests, pinned build, Twine, wheel inventory, and artifact upload.
3. Verify only the publish job has `id-token: write`, uses the protected `pypi` environment, downloads the verified artifact, and invokes the version-pinned PyPI publish action.
4. Verify manual dispatch cannot reach publication and a release tag must begin with `v` before the publish job runs.
5. Verify release workflow and documentation contain no PyPI API token, password, username, or secret interpolation contract.
6. Simulate a clean tagged v0.3.1 repository and verify preflight success; verify dirty, malformed/missing tag, mismatched Python/dbt versions, and unreleased/undated changelog states fail closed.
7. Verify release documentation covers owner setup, GitHub environment protection, PyPI trusted-publisher fields, release checklist/tag ordering, build-only validation, and post-publication checks.
8. Run YAML parsing, focused/full tests, build, Twine, wheel inventory, and v0.3.1 preflight simulation without commit, tag, release, publication, visibility change, or Snowflake mutation.

## REQ-011: additive v0.3.1 tutorial product readiness

1. Verify README and adopter docs use consistent v0.3.1 identity, parseable CLI examples, package-owned Orders names/paths, one-Agent smoke semantics, and accurate preview/apply/spend boundaries.
2. Generate the Orders starter twice from the same package version and explicit inputs in clean destinations; verify identical tracked content and manifest-owned Agent/eval metadata, synthetic-only data, no connection attempt, and fail-closed preservation unless overwrite is explicit.
3. Verify the starter surface exposes only the curated Orders tutorial and contains no generic wizard prompts, arbitrary-domain/schema inference, open-ended instruction generation, or reusable custom-starter framework.
4. Verify Agent render and deploy expose no projection selector, report one logical and physical identity, and render the complete Agent specification.
5. Verify general Agent smoke preview resolves logical Agent, physical Agent, request, and safety context without constructing a connector and works for Agents with no skills or eval model.
6. Verify applied general Agent smoke fails closed without the runtime extra, explicit connection, matching dbt-resolved database, target/database allowlists, and explicit apply; verify controlled human/JSON success and failure contracts when those inputs are faked.
7. Verify existing exposure/eval metadata, lifecycle/versioning behavior, artifact schemas, full-spec outputs, and skill smoke remain compatible except for the explicitly superseded projection contract.
8. Verify starter, render, deploy, and smoke default paths contain no connection, upload, Snowflake DDL, commit, alias, grant, invocation, eval, baseline, or spend side effect.
9. Run the package completion gate: version/docs alignment; starter regeneration; docs/policy and focused single-Agent deploy/smoke/compatibility tests; full Python tests; supported dbt dependency resolution and offline parse; full-spec render determinism; build, Twine, wheel inventory, clean installed-wheel smoke, and residue checks without credentials or Snowflake calls.
10. Verify no companion Cortex Code/catalog tutorial skill is created, published, installed, or required before the package completion gate passes.
11. For the deterministic Orders starter slice, verify exact generated paths, structured preview/apply
    actions, `.dbtignore` append/preservation, semantic-view dependency addition/preservation,
    identical-file no-ops, full collision validation before writes, and fail-closed differing files
    without force or a generic wizard.
12. For the single-Agent render/deploy slice, verify CLI and macros reject projection arguments,
    use one strict marked render envelope, expose the actual full specification, write deterministic
    contained artifacts, and preserve skill orchestration plus every existing apply safety gate.
13. For the general Agent smoke slice, verify required single logical Agent and nonblank question,
    optional exact expected-tool assertion, validated physical override and endpoint forwarding,
    stable structured preview/apply output, null preview result fields, and no preview invocation.
14. Verify applied general Agent smoke completes fresh manifest, explicit connection,
    manifest-database match, CLI target/database allowlists, and schema checks before reusing the
    existing invocation/SSE client; controlled assertion and runtime failures exit 2, and skill
    smoke behavior remains unchanged.
15. Verify the requirements index and REQ-011 status identify projection behavior as historical
    and superseded by REQ-013 rather than presenting it as the active v0.3.1 topology.

## REQ-013: single physical Agent evaluation

1. Verify an enabled exposure without evaluation metadata remains a valid normal deployment input and evaluation metadata is optional.
2. Verify deployment and every optional evaluation suite resolve the same single physical Agent FQN for one enabled exposure and target.
3. Verify evaluation cannot create, deploy, clone, suffix, replace, or otherwise mutate an Agent and fails closed when the manifest-owned deployed identity is not proven.
4. Verify adding, changing, disabling, or removing evaluation metadata does not change the deployed Agent specification or initiate lifecycle work.
5. Verify REQ-005, REQ-011, and REQ-012 retain historical facts while explicitly marking their distinct physical canonical/native-eval assumptions as superseded by REQ-013.
6. Verify capability evidence uses only `attached`, `invoked`, `completed_with_attachment`, `absent`, or `indeterminate`, and completion with an attachment is never promoted to invocation without trace or metric proof.
7. Verify the requirement records the supplied 7-record and 16-record zero-error probes, attached capabilities, absent `code_execution`, and indeterminate MCP evidence without claiming this slice reran Snowflake.
8. Verify historical `_EVAL` Agent histories remain auditable but cannot serve as candidate or accepted baselines for the single-FQN contract.
9. Verify public Agent render/deploy/smoke/grant/version/alias APIs and macros expose no projection selector, produce one full-spec target FQN, and retain skill, MCP, mutation, version, alias, and grant behavior.
10. Verify render artifacts use `renders/<target>/<agent>/spec.json`, `_EVAL` suffix generation and `cortex_agent_eval_suffix` are absent, and transitional eval compilation resolves the same FQN with only a fixed `single_agent` compatibility marker.
11. Run focused Agent/deploy/CLI/macro tests and offline dbt parse; do not run Snowflake, deployment, paid evaluation, consumer edits, commit, or push.
12. Verify eval metadata and the signed execution-plan identity contain no projection field, while optional suites resolve the same normal Agent FQN used by deployment.
13. Verify eval run proves Agent existence and DEFAULT version before config upload/START, invokes no Agent lifecycle macro, and uses the same FQN for native config, results, and provenance.
14. Verify schema-v2 candidate and baseline artifacts contain signed plan identity and pre/post DEFAULT provenance without projection, and version drift fails closed.
15. Verify legacy migration rejects a suffixed `_EVAL` physical identity rather than silently converting it to a current single-Agent baseline.
16. Verify focused evaluation documentation examples are checked against starter metadata, plan fields, and artifact schema fields rather than stale projection prose.
17. Verify general capability evidence uses only the five REQ-013 classifications and never derives `invoked` from attachment or completion alone.
18. Verify native `expected_tools` accepts declared Analyst, Cortex Search, `web_search`, and generic custom tool names while rejecting skills, MCP, `code_execution`, other capability tools, and undeclared names.
19. Verify `evaluation_supported` declarations are removed from focused metadata/reference examples and cannot alter rendered specification, target identity, or deployment behavior.
20. Verify the packaged Orders starter and integration mirror contain one Agent exposure and an optional unsuffixed `orders_assistant_core` eval model that targets that exposure.
21. Verify removing the optional Orders eval SQL/YAML still leaves an Agent-only fixture whose init, parse, manifest validation, render, and deploy preview path is documented and valid.
22. Verify the project skill never proposes a second Agent or projection-specific deployment, keeps evaluation authoring optional, and preserves the four existing approval stops and resume conditions.
23. Verify active README, upgrade, changelog release scope, getting-started, concept, lifecycle, evaluation, capability, CLI, macro, variable, metadata, compatibility, troubleshooting, and integration docs contain no active physical projection or `_EVAL` prerequisite claims.
24. Verify active installation text does not claim an unpublished PyPI artifact is available; historical requirement/regression references are allowed only when explicitly superseded.
25. Run focused docs/project-skill/starter/init/CLI tests, full package tests if feasible, offline dbt parse, build/Twine/wheel inventory, and hooks without Snowflake, spend, commit, or push.

## REQ-012: guided Cortex Code adoption skill

1. Verify exactly one project skill exists at `.cortex/skills/dbt-cortex-agent-project/SKILL.md`, is script-free, has valid frontmatter and required workflow/stopping/output sections, and is under 500 lines.
2. Verify the skill covers project discovery, objective/levers/data/proof, existing semantic-view adoption, the fixed Orders starter, existing-Agent migration, optional eval authoring, and manual command parity.
3. Verify every fenced `dbt-cortex-agent` command parses through the shipped 0.3.1 parser after deterministic placeholder substitution and none uses `--no-parse`.
4. Verify the skill contains no fixed sandbox, database, `dbt_focus`, connection, schema, warehouse, role, Agent, or evaluation environment value and does not duplicate lifecycle scripts or Agent DDL.
5. Verify explicit stops precede local writes, Snowflake mutation/runtime, paid eval, and baseline movement, with previews unable to satisfy a later approval.
6. Verify dbt Core/dbt-snowflake is authoritative and Fusion/fdbt is advisory.
7. Evaluate deterministic positive, near-miss, and negative prompt corpora against the frontmatter trigger contract; positive prompts select the skill and near-miss/negative prompts do not.
8. Verify README, adopter docs, compatibility, and changelog describe the project-local, non-published, script-free 0.3.1 guidance without implying live proof.
9. Run focused/full tests, build, wheel inventory, offline integration dependency/parse, and non-mutating starter/render/deploy/eval previews without Snowflake, spend, baseline movement, commit, or push.
10. Verify doctor accepts a full immutable Git SHA only when actual installed consumer dbt package metadata matches the CLI version; reject missing installed metadata, branch revisions, mismatched installed metadata, and semantic version mismatches while preserving semantic direct-match.

## REQ-014: installed-wheel single-Agent verifier

1. Verify the script creates a venv outside the checkout, installs the supplied wheel plus selected dbt pins, and proves the imported CLI module is not sourced from the checkout.
2. Verify two isolated consumer projects use a copied dbt package and installed starter data, with no project or dependency path into the checkout.
3. Verify Agent-only deps/parse/doctor/manifest/render/deploy-preview/smoke-preview succeeds with zero enabled evals and no eval command or macro.
4. Verify Agent-plus-eval completes the same path plus eval-plan preview and reports one identical Agent FQN across render, deploy, smoke, and eval evidence.
5. Verify both paths have the `single_agent` lifecycle marker, no projection field, no `_EVAL` identity, and identical rendered specifications.
6. Verify eval preview runs no lifecycle macro and does not change the rendered specification artifact; all commands omit connection, `--apply`, runtime, baseline, and paid actions.
7. Verify script unit tests fail closed for command failures, projection fields, FQN drift, lifecycle calls during eval, changed render artifacts, and eval metadata in the Agent-only path.
8. Verify package CI keeps Python 3.10-3.13 and dbt 1.10/1.11 matrices and runs the installed-wheel verifier in both dbt matrix entries.
9. Verify release workflow publication triggers, permissions, protected environment, and OIDC-only publish job remain unchanged and safe.
10. Run the local verifier, focused/full tests, build, Twine, wheel inventory, workflow YAML parse, and patch hygiene without Snowflake, consumer edits, commit, or push.
11. Run the exact tracked non-lock-file secret scan from the repository root and verify synthetic
    immutable Git SHA fixtures use only line-scoped allowlists, with no broad file or detector exclusion.
12. Run the workflow tracked-file scan and the absolute-path documentation test from outside the
    repository; verify both remain anchored to the package checkout and report no false self-findings.

## REQ-015: Authoritative Snow/dbt execution context

1. Resolve one file-based `SNOWFLAKE_JWT` connection into an isolated dbt child environment.
2. Verify explicit database and warehouse options override connection defaults while unrelated ambient values do not.
3. Reject missing connections, missing key files, and unsupported or conflicting authentication modes before execution.
4. Verify masked Snow CLI secret values are never forwarded and parent environment state is never mutated.
5. Verify manifest parse, Agent lifecycle macros, skill operations, dbt deps, and evaluation planning receive the same child environment.
6. Verify an installed wheel resolves a fake named connection and runs from outside the source checkout.

## REQ-019: Resource-scoped multi-database live proof

1. Verify the package live workflow has no pull-request trigger and requires the protected `snowflake-live-ci` environment.
2. Verify the workflow builds one wheel, records its SHA-256, and passes that exact artifact to the live verifier.
3. Verify two integration Agent models resolve to different approved databases with the same object name.
4. Verify partial allowlists fail before connection or mutation and complete allowlists permit the planned operation.
5. Verify live proof covers skill upload, Agent build, immutable version/alias capture, runtime smoke, eval-plan v2 preview, and a no-change second build.
6. Verify cleanup runs under `always()`, is idempotent, and removes only dedicated proof objects.
7. Verify retained evidence is whitelist-only and excludes credentials, account locators, prompts, answers, raw traces, and connection metadata.
8. Verify release publication requires the exact-wheel live-proof job while manual build-only dispatch remains non-publishing.

## REQ-020: Package-native Agent workflows

1. Verify `agent deploy` is preview-first, accepts repeated Agents and allowlists, and contains no Python Agent DDL.
2. Verify deploy preview parses once, resolves physical identities and skill uploads, and performs no connection, upload, build, or artifact write.
3. Verify deploy apply validates all Agent/stage databases before stage preflight, uploads skills, and runs dbt-owned deployment.
4. Verify multi-database and partial-failure output is deterministic and never claims transactional rollback.
5. Verify `eval verify` previews repeated suites and applies eval-model build, native evaluation, exact candidate consumption, and gating in order.
6. Verify intrinsic quality failure exits 1, missing baseline is valid, and infrastructure/configuration failure exits 2.
7. Verify explicit role/context handling remains backward compatible and unsupported authentication combinations are actionable.
8. Verify direct customer docs and installed-wheel proof contain no Makefile or adopter-script dependency.
