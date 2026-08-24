# Why Agents use a custom materialization

A Cortex Agent is a versioned application object, not a table or view. It still
benefits from model selection, graph dependencies, compilation, tests, and dbt's
target-aware relation naming. The package therefore represents an Agent as a
full-body dbt model with `materialized='cortex_agent'`.

The model body is the native Agent YAML specification. The model relation
determines the physical Agent FQN. No-output `ref()` calls establish Semantic
View and Search dependencies without placing those calls in the rendered YAML.

| Concern | Current model/materialization architecture |
|---|---|
| dbt representation | Full-body Agent model |
| Preview | `dbt compile --select <agent_model>` |
| Deployment | Approved `dbt build --select <agent_model>` |
| Versions/aliases | Materialization adapts LIVE to immutable `VERSION$N` and alias state |
| Lineage | Model `ref()` dependencies |
| Return value | No fake dbt relation |
| Default safety | Compile is offline; selected build is the mutation boundary |

The materialization validates the YAML mapping and orchestration settings,
enforces target/database allowlists and staged-skill readiness, hashes the final
specification plus skill state, skips unchanged versions, and reconciles LIVE,
the immutable version, alias, profile, and comment when change is required.

Legacy `exposures[].config.meta.cortex_agent` declarations remain readable for
migration compatibility. They are not the recommended authoring system and the
removed Python render/deploy lifecycle commands cannot deploy them.

## Manifest contract

The package resolves Agent models, semantic-view models, eval models, and
relation names from the dbt graph. Optional Python tooling reads only
`target/manifest.json`; source YAML is not reparsed.