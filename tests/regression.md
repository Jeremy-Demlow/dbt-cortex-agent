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