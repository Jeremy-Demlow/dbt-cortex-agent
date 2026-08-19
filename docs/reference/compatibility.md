# Compatibility

This matrix applies to `dbt_cortex_agent` 0.0.2 on both install surfaces.

The project-local Cortex Code adoption skill uses the same 0.0.2 CLI/parser and
metadata contracts. dbt Core with `dbt-snowflake` remains authoritative for its
proof steps; Fusion/fdbt output is advisory. The skill adds no runtime dependency,
is script-free, and adds no global installation or live-verification claim.
It ships in the same v0.0.2 release scope as the Orders starter,
single-Agent render/deploy, general Agent smoke, and immutable-SHA doctor
validation.

## Required

- dbt `>=1.10,<2.0` as declared by the package.
- Snowflake adapter for execution.
- Snowflake account features and privileges required by Cortex Agents and Agent
  Evaluation.

## Tested authority

| Component | Status |
|---|---|
| dbt Core 1.10.22 | Verified lower-bound dependency/parse path |
| dbt Core 1.11.11 | Authoritative package compile/artifact path |
| dbt-snowflake 1.10.3 | Verified lower-bound CI adapter |
| dbt-snowflake 1.11.4 | Verified reference CI adapter |
| dbt_semantic_view 1.0.5 | Verified reference dependency |
| Snowflake sandbox | Required for DDL, skills, versions, aliases, and eval execution |
| dbt Fusion 2.0.0-preview.203 | Advisory compile compatibility; not a release authority |
| DuckDB | Not supported or tested |

The CI matrix covers the lower accepted minor and the authoritative minor. Do not
infer that every accepted patch has live lifecycle coverage.

## Fusion boundary

Fusion can qualify dependency resolution, graph/metadata construction, package
macro resolution, and compilation. dbt Core/Snowflake remains authoritative until
normalized metadata, dependency edges, full-spec render output, and manifest compatibility
are demonstrated. Live `run_query`, Agent DDL, stage operations, and evaluations
remain Snowflake execution concerns.

### 2026-07-31 qualification result

The independent starter passed Fusion dependency resolution, parse, compile,
package-qualified generic-test discovery, Agent rendering, and structural eval
validation. Fusion produced manifest schema v12, which a strict manifest
compatibility adapter accepted unchanged.

Normalized parity with dbt Core 1.11.11/dbt-snowflake 1.11.4 passed for:

- resolved Agent and eval metadata,
- exposure/model/seed dependency edges,
- database, schema, and alias resolution,
- generic-test discovery,
- compiled semantic-view and eval models,
- full Agent JSON and optional eval-plan identity.

One relevant difference remains: Fusion omitted
`macro.dbt_cortex_agent.cortex_eval__assemble` from the eval model's manifest
`depends_on.macros`, while dbt Core recorded it. Because state-based CI uses graph
dependencies to widen Agent evaluation scope, Fusion artifacts are not an
authoritative replacement yet.

dbt Core 1.9.10/dbt-snowflake 1.9.4 cannot parse the integration fixture because
that line does not accept the modern generic-test `arguments` contract. The package
therefore requires `require-dbt-version: ">=1.10.0,<2.0.0"`. Fusion may
emit a package-compatibility warning because the range excludes 2.0. Widen it only
after macro dependency parity is resolved and the complete release gate passes.
