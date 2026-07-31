# Troubleshooting

| Symptom | Check |
|---|---|
| No enabled exposure found | `enabled: true` and exact exposure name |
| Semantic model does not resolve | Model name is unique and `materialized='semantic_view'` |
| Package macro undefined in model SQL | Call it as `dbt_cortex_agent.<macro>` |
| Custom macro undefined in `agent.yml` | Property YAML supports `target`, `var`, `env_var`, not package macros |
| Wrong deploy target | Match `target.name` to `cortex_agent_deploy_target` or use dry run |
| Missing staged `SKILL.md` | Upload the declared local skill directory to the exact stage path |
| Render contains `$$` | Remove the delimiter from instructions/config content |
| Expected eval tool missing | Confirm projection and `evaluation_supported` flags |
| Eval table invalid | Materialize `INPUT_QUERY` and `OUTPUT` VARIANT; run live validation |
| Tool metrics fail on boundary rows | Ensure `custom_criteria.test_type` is set correctly |
| Eval render needs Snowflake | Config rendering hashes table content and checks dataset inventory |
| MCP not attached after no-change skip | Review MCP state and use intentional force only when needed |
| Unexpected `_EVAL` or environment suffix | Review naming map and suffix vars |

For client-side retries, durable JSON artifacts, accepted baselines, and CI scoping,
use the optional framework tooling rather than the package-native eval loop alone.
