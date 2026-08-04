# CLI reference (v0.3.0)

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
`--package-source`, `--revision` (default `v0.3.0`), `--agent-schema`,
`--eval-schema`, both repeatable allowlists, `--apply`, and `--run-dbt-deps`.
Output is messages or JSON with `applied`, `changed_files`, and `messages`.

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

## Agent lifecycle

### `dbt-cortex-agent agent render`

Render canonical specs. Options: shared options and repeatable `--agent`.

### `dbt-cortex-agent agent deploy` — MUTATION with `--apply`

Dry-run or deploy/version. Options: shared options, repeatable `--agent`,
`--alias`, both allowlists, and `--apply`.

### `dbt-cortex-agent agent grant` — MUTATION with `--apply`

Dry-run or grant Agent usage. Options: shared options, repeatable `--agent`, both
allowlists, and `--apply`.

### `dbt-cortex-agent agent promote` — MUTATION with `--apply`

Move an alias. Options: shared options, repeatable `--agent`, required
`--from-alias`, required `--to-alias`, both allowlists, and `--apply`.

### `dbt-cortex-agent agent rollback` — MUTATION with `--apply`

Move an alias to an immutable version. Options: shared options, repeatable
`--agent`, required `--alias`, required `--to-version`, both allowlists, and
`--apply`.

## Evaluations

### `dbt-cortex-agent eval run` — PAID with `--apply`

Render a plan or execute existing native prerequisites. Options: shared options,
required `--agent`, required `--suite`, `--run-name`, `--poll-attempts` (60),
`--poll-interval` (30), `--transient-retries` (1), and `--apply`. Applied
execution requires `--connection` and the `runtime` extra.
It also requires `--warehouse`.

### `dbt-cortex-agent eval compare BASELINE CANDIDATE`

Compare artifacts. Options: shared options and `--tolerance` (0.01). Emits JSON;
exit `1` when comparison fails.

### `dbt-cortex-agent eval accept-baseline CANDIDATE` — MUTATION with `--apply`

Preview or write a baseline. Options: shared options, `--baseline-dir`, `--apply`,
and `--force`; `--force` requires `--apply`.

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