# dbt and Python ownership boundary

`dbt_cortex_agent` is one product with two implementation layers. dbt is the system of record; Python is a local and remote coordinator that consumes dbt-owned contracts.

| dbt owns | Python owns |
|---|---|
| Resolved graph and `meta` contracts | Local files and manifest consumption |
| Agent and eval validation and rendering | Installed CLI and Snow CLI coordination, including skill upload |
| Agent DDL and physical naming | REST/SSE client execution |
| LIVE versions, immutable versions, aliases, and grants | Polling, bounded retry, and result collection |
| Eval-plan and native-eval projection rendering | Local artifacts, accepted baselines, and comparisons |
| Public lifecycle macros | Thin delegation to public dbt macros |

Python must not implement mutating Agent DDL or reconstruct a second metadata model. Agent deploy, grant, promotion, and rollback enter Snowflake through package macros. Python may prepare local inputs, coordinate external clients, invoke those macros, and persist local evidence around the operation.
