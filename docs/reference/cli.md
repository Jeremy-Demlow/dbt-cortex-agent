# CLI reference (v0.0.6)

`dbt-cortex-agent` is the single console entry. Manifest-dependent commands run
a fresh `dbt parse` unless `--no-parse` is supplied for a controlled fixture.

## Process contract

| Exit | Meaning |
|---:|---|
| `0` | success or passing gate |
| `1` | doctor diagnostic or evaluation gate failed |
| `2` | controlled configuration, filesystem, connector, HTTP, or runtime error |

Applicable commands emit human text by default and machine-readable stdout with
`--json`. Controlled errors go to stderr. Mutation, runtime, and spend commands
are preview/dry-run by default and require `--apply`.

## Shared options

| Option | Purpose |
|---|---|
| `-h`, `--help` | Show command help. |
| `--version` | Print CLI version. |
| `--project-dir` | dbt project; default current directory. |
| `--manifest` | Manifest path relative to project; default `target/manifest.json`. |
| `--target` | Explicit dbt target. |
| `--connection` | Explicit Snowflake connection; required as a flag for applied remote operations. |
| `--database` | Expected Snowflake target database. |
| `--schema` | Agent schema for runtime operations. |
| `--role` | Expected Snowflake execution role. |
| `--warehouse` | Warehouse for paid evaluation. |
| `--artifact-dir` | Local eval artifact root; default `target/dbt_cortex_agent`. |
| `--dbt-executable` | dbt executable; default `dbt`. |
| `--snow-executable` | Snow CLI executable; default `snow`. |
| `--json` | Emit structured JSON where supported. |
| `--no-parse` | Skip parse only for controlled fixtures; unsafe for normal use. |
| `--allow-target` | Repeatable mutation/runtime target gate. |
| `--allow-database` | Repeatable mutation/runtime database gate. |
| `--apply` | Cross the command's labeled mutation/runtime/paid boundary. |

Precedence is CLI option, then environment variable, then built-in default.

## Bootstrap and diagnostics

### `dbt-cortex-agent init` — MUTATION with `--apply`

Preview or append missing package/project-var entries. Options: shared options,
`--package-source`, `--revision` (default `v0.0.6`), `--agent-schema`,
`--eval-schema`, both repeatable allowlists, `--apply`, and `--run-dbt-deps`.
Output is messages or JSON with `applied`, `changed_files`, and `messages`.
By default, the command configures an existing dbt project only; it does not scaffold a dbt
project, full-body Agent model, semantic view, evaluation model, seed, or skill.
`--starter` with value `orders` selects the only curated starter and adds structured `starter`
and `actions` fields to JSON output. It plans exact package-owned paths, appends
`.dbtignore` and the semantic-view dependency when needed, validates all
collisions before writes, and has no force or generic wizard behavior.

### `dbt-cortex-agent doctor`

Run local executable, project, manifest, safety, and optional connection
diagnostics. Options: shared options. Output is status lines or JSON diagnostics;
exit `1` if any diagnostic is `FAIL`.

## Manifest

### `dbt-cortex-agent manifest validate`

Validate freshly resolved metadata. Options: shared options and repeatable
`--agent`. Output identifies the manifest and selected logical Agents.

## Skills

### `dbt-cortex-agent skill plan`

Build a non-mutating upload plan. Options: shared options and repeatable `--agent`.

### `dbt-cortex-agent skill upload` — MUTATION with `--apply`

Preview or upload through Snow CLI. Options: shared options, repeatable `--agent`,
both repeatable allowlists, and `--apply`.

### `dbt-cortex-agent skill smoke` — RUNTIME with `--apply`

Preview mappings or invoke live Agents. Options: shared options, repeatable
`--agent`, `--agent-object`, `--endpoint`, both allowlists, and `--apply`.
Applied smoke requires `--connection`, database, schema, and the `runtime` extra.

## Agent lifecycle and runtime

Agent rendering and deployment remain dbt operations. The package can sequence
deployment without becoming a second DDL authority.

### `dbt-cortex-agent agent scaffold` — LOCAL MUTATION with `--apply`

Preview or create a generic full-body Agent model, metadata file, and skill
directory. `--semantic-view-model` optionally adds an Analyst tool;
`--with-eval` optionally adds an editable suite. A Semantic View is not required.
Private-preview experimental keys remain user-authored YAML, not CLI options.

### `dbt-cortex-agent agent versions` — READ ONLY

Inspect immutable versions, aliases, DEFAULT, LAST, and LIVE through a dbt macro.
Requires an explicit connection because it reads Snowflake state.

### `dbt-cortex-agent agent promote` and `dbt-cortex-agent agent rollback` — MUTATION with `--apply`

Preview an immutable `VERSION$N`, alias, and optional `--set-default`; apply
delegates routing to dbt and verifies postconditions. Rollback preserves newer
versions.

### `dbt-cortex-agent agent drop` — DESTRUCTIVE with `--apply`

Retire exactly one manifest-owned Agent. Apply requires exact physical-FQN
confirmation, connection, target/database allowlists, dbt-owned DDL, and absence
verification. Dependent data objects, source, stages, and evaluation evidence remain.

### `dbt-cortex-agent agent deploy` — MUTATION with `--apply`

Preview selected physical Agents, skill uploads, and dependency-aware dbt
selectors. Applied execution requires an explicit connection and complete
target/database allowlists, preflights and uploads skills, then runs dbt build.
The workflow is non-transactional and reports possible partial application if
dbt fails after upload. No Makefile or adopter Python wrapper is required.

### `dbt-cortex-agent agent smoke` — RUNTIME with `--apply`

Preview or invoke one manifest-owned Agent without requiring a skill declaration.
Required options are one logical `--agent` and a nonblank `--question`. Optional
options are `--expect-tool` for an exact returned tool-name assertion, `--version`
for a committed version, alias, or shortcut,
`--agent-object` for a physical Agent override, `--endpoint`, both repeatable
allowlists, and `--apply`.

Preview resolves physical identity from manifest target naming or validates the
explicit override. It does not construct a connector or invoke the Agent. JSON
always contains `command`, `applied`, `agent`, `agent_object`, `question`,
`expected_tool`, `passed`, and `response`; preview sets the final two fields to
`null`. Apply requires a fresh manifest, explicit `--connection`, database/schema,
the configured database matching dbt's resolved database, and CLI target/database
allowlists. It reuses the package's bounded SSE invocation client. Runtime,
configuration, and expected-tool assertion failures exit `2`.

## Evaluations

### `dbt-cortex-agent eval verify` — PAID with `--apply`

Preview an Agent and one or more repeatable `--suite` selections. Applied
execution materializes and tests each eval model, runs native evaluation,
consumes the exact candidate, and gates against an established baseline when
present. Missing baselines use intrinsic thresholds and report
`baseline_state=not_established`. Quality failure exits `1`; controlled
configuration or runtime failure exits `2`. Baseline acceptance stays separate.

### `dbt-cortex-agent eval run` — PAID with `--apply`

Render a plan or execute existing native prerequisites. Options: shared options,
required `--agent`, required `--suite`, `--run-name`, `--poll-attempts` (60),
`--poll-interval` (30), `--transient-retries` (1), and `--apply`. Applied
execution requires `--connection` and the `runtime` extra.
It also requires `--warehouse`, both repeatable allowlists, and a configured
target/database matching the dbt-rendered plan. Applied execution sets the
plan's authoritative target role before warehouse, database, and schema.
The command does not deploy or alter the Agent and does not materialize the eval model.
Applied candidates default to
`<artifact-dir>/candidates/<agent>/<suite>/<run_name>.json`.

### `dbt-cortex-agent eval compare BASELINE CANDIDATE`

Compare artifacts. Options: shared options and `--tolerance` (0.01). Emits JSON;
exit `1` when comparison fails.

### `dbt-cortex-agent eval accept-baseline CANDIDATE` — MUTATION with `--apply`

Preview or write a baseline. Options: shared options, `--baseline-dir`, `--apply`,
and `--force`; `--force` requires `--apply`.
The default target is
`<artifact-dir>/baselines/<agent>/<suite>.json`.

### `dbt-cortex-agent eval gate CANDIDATE`

Gate thresholds and baseline policy. Options: shared options, `--baseline`,
`--baseline-dir`, and `--tolerance` (0.01). Emits JSON; exit `1` on failure.

## Environment variables

| Variable | CLI destination |
|---|---|
| `DBT_PROJECT_DIR` | `--project-dir` |
| `DBT_MANIFEST` | `--manifest` |
| `DBT_TARGET` | `--target` |
| `SNOWFLAKE_CONNECTION_NAME` | `--connection` value only; does not satisfy explicit apply gate |
| `SNOWFLAKE_DATABASE` | `--database` |
| `SNOWFLAKE_SCHEMA` | `--schema` |
| `SNOWFLAKE_WAREHOUSE` | `--warehouse` |
| `DBT_CORTEX_AGENT_ARTIFACT_DIR` | `--artifact-dir` |
| `DBT_EXECUTABLE` | `--dbt-executable` |
| `SNOW_EXECUTABLE` | `--snow-executable` |