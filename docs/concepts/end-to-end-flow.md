# End-to-end architecture flow

`dbt_cortex_agent` 0.0.6 has two shipped surfaces and one metadata authority:

- **dbt package:** full-body Agent materialization, eval contracts, graph
  resolution, deterministic rendering, lifecycle DDL, and versioning;
- **Python CLI:** project diagnostics, local skill files/Snow CLI, runtime smoke,
  evaluation clients, process exits/JSON, recovery, and artifacts;
- **consumer project:** Agent, Semantic View, Search, and eval models; skills;
  target policy; profiles; CI approvals; and accepted baselines.

```text
AUTHORING [consumer dbt project]
  generic or capability-backed full-body Agent model: materialized='cortex_agent'
  eval table model:      config.meta.cortex_eval
  Semantic View/Search models and skill folders
                         |
                         v
                  dbt deps + dbt parse
                         |
           +-------------+--------------+
           |                            |
           v                            v
 dbt compile/build                 target/manifest.json
 preview/materialize                     |
           |                            v
           |                    Python companion
           |                 skills/smoke/eval/artifacts
           +-------------+--------------+
                         |
                         v
               LIVE -> VERSION$N -> alias
                         |
              +----------+-----------+
              |                      |
              v                      v
       runtime/smoke proof      OPTIONAL EVALUATION
                               table run/test
                               start/poll/recover
                               candidate -> gate -> baseline
```

## Manifest ownership

dbt is the system of record. The model relation determines the physical Agent
FQN, the body is the native specification, and no-output `ref()` calls establish
dependencies. Python runs a fresh parse and consumes `target/manifest.json`; it
does not invent another Agent definition.

## Agent lifecycle

`dbt compile --select <agent>` is the non-mutating preview. An approved
dependency-aware `dbt build --select +<agent>` invokes the materialization. It
verifies staged skills, hashes spec plus skill state, skips unchanged versions,
or modifies LIVE and commits an immutable version before reconciling alias,
profile, and comment. It returns no fake table/view relation.

Python does not implement Agent DDL. Package lifecycle commands validate and
coordinate real dbt macros for version inventory, alias/default routing, and
guarded retirement.

## Optional evaluation

Evaluation metadata targets the same model-selected Agent. Applied `eval run`
assumes both Agent and eval table already exist, then starts, polls, recovers when
possible, and writes a provenance-bound candidate artifact. Paid evaluation is
never part of main reconciliation or an implicit Agent build.

## CI proof order

1. Pull request: dependency resolution, parse, tests, compile, and affected scope.
2. Approved PR lane: affected Agent deploy/smoke and optional paid evaluation.
3. Main: optional DCM infrastructure first, then every enabled Agent plus current
   eval table materialization/tests; no paid evaluation.
4. Human policy: separately approve baseline movement or an operational alias.