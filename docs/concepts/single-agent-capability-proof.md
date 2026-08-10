# Single-Agent capability proof

One exposure owns one full deployed Agent specification. Evaluation metadata is
optional and does not create or filter a second Agent.

## Attachment evidence

The deployed Agent may include:

- all declared tools,
- web search and data-to-chart,
- globally enabled code execution,
- staged skills,
- MCP attachment through separate DDL.

Offline metadata and rendered-spec inspection classify these capabilities as
`attached` or `absent`. A completed run while a capability is attached is
`completed_with_attachment`; it is not invocation proof. `invoked` requires trace
or metric evidence. Use `indeterminate` when the available evidence cannot establish
attachment or invocation, including MCP when only the exposure declaration is known.

## Built-in evaluation coverage

Expected native tool invocations may name declared:

- Analyst tools,
- Cortex Search tools,
- the fixed `web_search` tool,
- generic custom tools.

Skills completed in live probes remain `completed_with_attachment` unless a
trace or metric proves invocation. MCP may remain attached, but built-in evaluation
does not invoke it. `code_execution` cannot be claimed as native expected-tool
coverage and remains unresolved when deployed proof is absent. Do not weaken or
filter the deployed Agent specification for evaluation.
