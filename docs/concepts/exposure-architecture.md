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
| Deployment | `agent deploy` delegates an approved dependency-aware build to dbt |
| Versions/aliases | Materialization adapts LIVE to immutable `VERSION$N` and alias state |
| Lineage | Model `ref()` dependencies |
| Return value | No fake dbt relation |
| Default safety | Compile does not run the Agent materialization, but can connect and writes local artifacts; selected build is the mutation boundary |

The materialization validates the YAML mapping and orchestration settings,
enforces target/database allowlists and staged-skill readiness, hashes the final
specification plus skill state, skips unchanged versions, and reconciles LIVE,
the immutable version, alias, profile, and comment when change is required.

Legacy exposure-based declarations are historical architecture, not a supported
public authoring or deployment contract. Current discovery selects full-body
models materialized as `cortex_agent`.

## Manifest contract

The package resolves Agent models, semantic-view models, eval models, and
relation names from the dbt graph. Optional Python tooling reads only
`target/manifest.json`; source YAML is not reparsed.