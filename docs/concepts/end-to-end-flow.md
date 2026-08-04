# End-to-end architecture flow

`dbt_cortex_agent` 0.3.0 has two shipped surfaces and one metadata authority:

- **dbt package:** Agent/eval contracts, graph resolution, deterministic renders,
  lifecycle DDL, versioning, grants, and native evaluation macros;
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
        +----------------+-------------------+
        |                                    |
        v                                    v
 CANONICAL LIFECYCLE                  NATIVE EVALUATION
 skill plan/upload                    native_eval render/deploy
 canonical render/deploy              materialize/test eval table
 spec + skill hashes                  render one execution plan
 LIVE -> VERSION$N -> alias           start/poll paid evaluation
 grants/promotion/rollback            candidate -> gate -> baseline
        |                                    |
        v                                    v
 separate live skill smoke            durable local evidence
```

## Manifest ownership

dbt is the system of record. Package macros read the in-memory graph; the CLI
runs a fresh parse and reads only `target/manifest.json`. It never reparses source
YAML into another Agent/eval model. This keeps database/schema/alias resolution,
dependencies, physical Agent names, eval tables, and skill declarations aligned.

`--no-parse` exists only for controlled fixtures with a deliberately supplied
manifest. It is not an operational performance switch.

## Canonical lifecycle

The installed CLI and public macros expose the same deploy semantics. For skills,
the operator plans and uploads local directories before canonical deploy. The
macro independently verifies staged `SKILL.md`, hashes final spec plus staged
skill state, skips unchanged versions, or modifies LIVE and commits an immutable
version. Alias movement, grants, MCP attachment, and smoke are explicit concerns.

The CLI does not implement Agent DDL. It delegates lifecycle changes to public
dbt macros with selected Agents and explicit dry-run/apply arguments.

## Native evaluation

The `native_eval` projection derives a separate evaluator-compatible Agent from
the same exposure. It uses the configured suffix (default `_EVAL`), excludes
skills and MCP connectors, and excludes tools/code execution explicitly marked
unsupported while retaining supported instructions, tools, model, and budget.

The CLI's `eval run` first consumes one offline `cortex_eval__execution_plan`
containing Agent/table/stage identity, native config, metrics, policy, ordered
refs, target context, and suite signature. Paid apply assumes the native-eval
Agent and materialized eval table already exist; it creates/uses the config stage,
starts/polls the evaluation, and writes provenance-bound candidate JSON. The dbt
`cortex_eval__run` macro is a separate on-demand native loop without local
accepted-baseline artifacts.

## CI proof order

1. PR: dependencies, parse, tests, doctor, manifest validation, deterministic
   renders, dry-run deploy/upload, and eval plan—no mutation or spend.
2. Sandbox: approved skill upload, canonical/native-eval deploy, eval table
   materialization/tests, grants, and optional live smoke.
3. Paid eval: approved `eval run --apply`, candidate gate, artifact retention.
4. Human policy: separately approve baseline acceptance or production alias move.

## Integration proof boundary

The package-local [`integration_tests`](../../integration_tests/README.md)
consumer proves dependency installation, dbt parsing, semantic/eval compilation
where a profile is available, manifest-owned metadata, package-qualified tests,
and deterministic canonical/native-eval plans.

It does not prove account privileges, live Agent DDL/versioning, stage upload,
runtime skill selection, MCP attachment, or paid Agent Evaluation unless those
steps are explicitly enabled against an isolated sandbox.