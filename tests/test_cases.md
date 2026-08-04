# Test cases

## REQ-002: v0.3.0 identity and Python ownership

1. Verify package metadata, runtime version, lock data, bootstrap default, citation, and current installation docs identify v0.3.0 while the v0.2.0 changelog remains historical.
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

1. Verify the root README contains product identity, two v0.3.0 install surfaces, compatibility, non-mutating quickstart, controlled deploy, CLI-versus-macro guidance, lifecycle/eval overview, docs map, limitations, and policies.
2. Verify every shipped command and command-specific option appears in the CLI reference and mutation/runtime/spend commands are labeled from parser help.
3. Verify all documented local Markdown links resolve and adopter docs contain no copied-tooling, repository-only Make, embedded-package, or contradictory release-status language.
4. Verify package, README, installation, compatibility, CLI, and upgrade surfaces identify v0.3.0 while upgrade history may identify v0.2.0.
5. Verify YAML exposure/eval examples parse and preserve the manifest-owned metadata locations and required fields.
6. Verify quickstart CLI examples parse through the shipped parser and contain no `--apply`, runtime smoke, baseline write, or paid evaluation execution.
7. Verify evaluation docs state that the CLI requires a materialized eval table, stage, and deployed native-eval Agent and does not create those prerequisites.
8. Run docs tests, the full Python suite, package build, and integration-consumer dbt parse without live mutation, runtime invocation, or paid evaluation.

## REQ-008: standalone CI and release verification

1. Verify one active root package workflow runs on pull request, push, and manual dispatch with read-only permissions and no nested workflow files.
2. Verify workflow text contains no secret interpolation, Snowflake credential variables, private-key setup, `--apply`, live runtime smoke, baseline acceptance, or paid evaluation.
3. Verify the Python matrix exactly covers 3.10, 3.11, 3.12, and 3.13 and package metadata declares the same range.
4. Verify the dbt matrix pins lower-bound dbt-core 1.10 with dbt-snowflake 1.10.3 and authority dbt-core 1.11 with dbt-snowflake 1.11.4, consistent with `dbt_project.yml`; dbt 1.9 is excluded by integration-fixture evidence.
5. Verify policy/docs/project health, full tests, byte-compilation, dbt dependency/parse, macro determinism, canonical/native-eval fixture preview, eval-plan preview, and dry-run lifecycle are required jobs or steps.
6. Verify version alignment, pyproject/dbt consistency, package inventory, generated-residue, and secret-scan guards are present and tested.
7. Build sdist and wheel, run Twine checks, inspect wheel inventory, and install the wheel into a clean environment outside the checkout.
8. Exercise installed CLI help/version and deterministic consumer fixture previews without a connection, mutation, runtime invocation, or spend.
9. Generate pinned dependency-license and CycloneDX SBOM artifacts outside the checkout.
10. Run focused/full tests and local build/install checks, then remove dbt, build, cache, license, and SBOM residue from the checkout.
