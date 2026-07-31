# Canonical versus native-eval projections

One exposure owns both projections.

## Canonical

Represents intended Agent behavior and can include:

- all declared tools,
- web search and data-to-chart,
- globally enabled code execution,
- staged skills,
- MCP attachment through separate DDL.

## Native eval

Targets built-in Cortex Agent Evaluation and:

- appends the configured eval suffix to the Agent name,
- excludes tools/capabilities with `evaluation_supported: false`,
- excludes skills,
- excludes MCP connectors.

Evaluation metadata validates expected tools against the selected projection. Do
not weaken the canonical Agent merely to satisfy the built-in evaluator.
