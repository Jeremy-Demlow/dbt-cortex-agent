# Why Agents are exposures

A Cortex Agent is a versioned application object, not a relation. It has LIVE
state, immutable versions, aliases, staged skills, MCP attachments, and grants.
The package therefore uses an exposure as the declarative system of record and an
explicit macro for lifecycle mutation.

| Concern | Exposure architecture | Fake relation materialization |
|---|---|---|
| dbt representation | Application dependency | View/table-shaped proxy |
| Deployment | Explicit guarded macro | Selected model execution |
| Versions/aliases | First-class lifecycle | Difficult to map to relation replacement |
| Grants/MCP | Separate typed DDL | Often hidden in hooks |
| Lineage | Exposure `depends_on` | Model `ref()` |
| Default safety | Dry-run and target guard | Mutation on `dbt run/build` |

Semantic views and eval datasets remain dbt models because they are analytical
objects with real graph-managed SQL definitions.

## Manifest contract

The package resolves Agent metadata, semantic-view models, eval models, and
relation names from the dbt graph. Optional Python tooling reads only
`target/manifest.json`; source YAML is not reparsed.
