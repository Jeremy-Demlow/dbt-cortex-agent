# dbt and Python ownership boundary

`dbt_cortex_agent` is one product with two deliberately narrow implementation
layers. dbt is the system of record and the only Agent lifecycle authority.
Python coordinates file-based skills, runtime smoke, and evaluations.

| dbt owns | Python owns |
|---|---|
| Resolved graph and `meta` contracts | Local files and manifest consumption |
| Agent model validation and materialization | Skill file planning and upload |
| Agent DDL, physical naming, versions, aliases, profile, and comments | REST/SSE runtime and skill smoke |
| LIVE versions, immutable versions, aliases, and grants | Polling, bounded retry, and result collection |
| Same-Agent eval-plan rendering | Local artifacts, accepted baselines, and comparisons |
| Materialization and evaluation-plan macros | Paid evaluation coordination |

Python must not render, create, alter, commit, alias, grant, promote, or roll back
model-backed Agents. It must not provision infrastructure such as internal
stages. Agent lifecycle enters Snowflake only through `dbt build` and the
`cortex_agent` materialization. Python may validate and upload local skill files
to an existing managed stage, invoke runtime clients, coordinate evaluation, and
persist local evidence.
