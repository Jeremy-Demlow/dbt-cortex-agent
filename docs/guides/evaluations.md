# Evaluations

An eval suite is a table model with `config.meta.cortex_eval`. The model computes
ground truth in SQL and materializes `INPUT_QUERY` plus `OUTPUT` VARIANT rows.

## Package-native capabilities

- validate metadata and live dataset shape,
- render/start an Agent Evaluation,
- poll and write a Snowflake results table,
- enforce declared metric thresholds,
- test question refs, boundary minimums, and expected-tool coverage.

## Optional framework capabilities

Copyable Python tooling adds client-side retry, durable JSON artifacts, accepted
baseline comparison, suite-signature checks, and changed-Agent CI scoping.

| Capability | Package macros | Framework tooling |
|---|---:|---:|
| Config/start/poll/results | Yes | Yes |
| Threshold gate | Yes | Yes |
| Retry transient failures | No | Yes |
| Durable JSON | No | Yes |
| Accepted-baseline comparison | No | Yes |
| State-scoped CI | No | Yes |

## Important behavior

- Boundary rows may have no ground-truth invocation.
- Tool metrics should gate only in-scope rows.
- Package model-SQL helpers must be called package-qualified.
- `cortex_eval__render_config` can query the materialized table and Snowflake
  dataset inventory; it is not an unconditional offline operation.
- Live evaluation incurs Cortex spend and must be explicitly approved.
