# Test cases

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
2. Verify Python parses exactly one schema-v1 plan from `dbt run-operation` output after fresh parse and preserves injectable plan/command fakes.
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
