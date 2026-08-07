# Regression tests

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
- Fix summary: docs now describe the current v0.3.0 boundaries, artifact paths, and troubleshooting order, and the fixture explicitly allowlists only its documented sandbox database.
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