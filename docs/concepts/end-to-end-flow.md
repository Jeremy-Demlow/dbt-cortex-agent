# End-to-end architecture flow

`dbt_cortex_agent` 0.0.2 has two shipped surfaces and one metadata authority:

- **dbt package:** Agent/eval contracts, graph resolution, deterministic renders,
  lifecycle DDL, versioning, grants, and built-in evaluation macros;
- **Python CLI:** fresh-manifest coordination, local skill files/Snow CLI,
  connector-backed runtime/evaluation clients, process exits/JSON, and artifacts;
- **consumer project:** exposures, semantic/eval models, skills, target policy,
  profiles, roles, objects, CI approvals, and accepted baselines.

## Control plane

```text
AUTHORING [consumer dbt project]
  Agent exposure: config.meta.cortex_agent
  eval table:     config.meta.cortex_eval
  semantic views, tool dependencies, optional skills
                         |
                         v
                  dbt deps + dbt parse
                         |
           +-------------+--------------+
           |                            |
           v                            v
   dbt package macros             target/manifest.json
   validate/render/DDL                   |
           |                            v
           |                 installed dbt-cortex-agent CLI
           |                 select/coordinate/artifact
           +-------------+--------------+
                         |
                         v
                  ONE AGENT LIFECYCLE
                  skill plan/upload
                  full-spec render/deploy
                  spec + skill hashes
                  LIVE -> VERSION$N -> alias
                  grants/promotion/rollback
                         |
              +----------+-----------+
              |                      |
              v                      v
       runtime/smoke proof      OPTIONAL EVALUATION
                               materialize/test eval table
                               render one execution plan
                               start/poll paid evaluation
                               candidate -> gate -> baseline
```

## Manifest ownership

dbt is the system of record. Package macros read the in-memory graph; the CLI
runs a fresh parse and reads only `target/manifest.json`. It never reparses source
YAML into another Agent/eval model. This keeps database/schema/alias resolution,
dependencies, physical Agent names, eval tables, and skill declarations aligned.

`--no-parse` exists only for controlled fixtures with a deliberately supplied
manifest. It is not an operational performance switch.

## Agent lifecycle

The installed CLI and public macros reach the same deploy macro, but
their orchestration safety differs. Applied CLI deploy plans and uploads declared
local skills first, then delegates with fresh-manifest, explicit-connection,
resolved-database, and CLI allowlist gates. A direct macro call performs none of
that local orchestration and relies on dbt profile context plus package safety
vars. The macro independently verifies staged `SKILL.md`, hashes final spec plus staged
skill state, skips unchanged versions, or modifies LIVE and commits an immutable
version. Alias movement, grants, MCP attachment, and smoke are explicit concerns.

The CLI does not implement Agent DDL. It delegates lifecycle changes to public
dbt macros with selected Agents and explicit dry-run/apply arguments. Render
parses one dbt-owned marked payload and saves only the returned specification at
`target/dbt_cortex_agent/renders/<target>/<agent>/spec.json`.

## Optional evaluation

Evaluation metadata is optional and resolves the same target-selected physical
Agent as deployment. It does not filter the specification or create, deploy,
clone, or suffix an Agent. The CLI's `eval run` first consumes one offline
`cortex_eval__execution_plan`
containing Agent/table/stage identity, native config, metrics, policy, ordered
refs, target context, and suite signature. Paid apply assumes the normal Agent
and materialized eval table already exist; it creates/uses the config stage,
starts/polls the evaluation, and writes provenance-bound candidate JSON. The dbt
`cortex_eval__run` macro is a separate on-demand built-in loop without local
accepted-baseline artifacts.

## CI proof order

1. PR: dependencies, parse, tests, doctor, manifest validation, deterministic
   renders, dry-run deploy/upload, and eval plan—no mutation or spend.
2. Sandbox: approved skill upload, one Agent deploy, optional eval table
   materialization/tests, grants, and optional live smoke.
3. Paid eval: approved `eval run --apply`, candidate gate, artifact retention.
4. Human policy: separately approve baseline acceptance or production alias move.

## Integration proof boundary

The package-local [`integration_tests`](../../integration_tests/README.md)
consumer proves dependency installation, dbt parsing, semantic/eval compilation
where a profile is available, manifest-owned metadata, package-qualified tests,
and deterministic Agent/eval plans.

It does not prove account privileges, live Agent DDL/versioning, stage upload,
runtime skill selection, MCP attachment, or paid Agent Evaluation unless those
steps are explicitly enabled against an isolated sandbox.