# Eval metadata reference

Eval metadata lives at `models[].config.meta.cortex_eval` on a table model.

## Required fields

| Field | Type | Contract |
|---|---|---|
| `name` | string | Suite name |
| `agent` | string | Enabled Agent exposure name |
| `metrics` | non-empty list | Built-in names or custom metric objects |
| `questions` | non-empty list | Suite contract rows |

## Optional fields and complete nested inventory

| Field path | Type | Required | Default / consumer |
|---|---|---:|---|
| `description` | string | No | `Automated evaluation` |
| `metrics[]` | string/object | Yes | At least one entry |
| `metrics[].name` | string | Custom metric only | Custom metric identifier |
| `metrics[].prompt` | string | Custom metric only | Judge prompt |
| `metrics[].score_ranges` | mapping | No | Passed through to built-in evaluation |
| `thresholds.<metric>` | number | No | Package-native hard floor |
| `regression_tolerances.<metric>` | number | No | Optional Python baseline comparison only |
| `questions[]` | object | Yes | At least one entry |
| `questions[].id` | string | Yes | Question identifier |
| `questions[].test_type` | string | Recommended | `in_scope`, `out_of_scope`, or `negative` |
| `questions[].expected_tools[]` | string | No | Declared native-supported tool name |
| `questions[].ground_truth_ref` | string | Yes | Must map to exactly one live dataset row |

Custom metrics require `name` and `prompt`. `thresholds` are used by package-native
gating. `regression_tolerances` are consumed by the shipped CLI comparison and gate commands.

Each question requires `id` and `ground_truth_ref`. `expected_tools` may name a
declared Analyst tool, Cortex Search tool, generic custom tool, or the fixed
`web_search` name for the same target-resolved Agent FQN. A declared generic tool
such as `StaffingSimulator` is validated by its package-level type and name. Skills,
MCP connectors, `code_execution`, and other capability tools cannot be claimed as
native coverage; use smoke, integration, trace, or other capability-specific proof.
Use `test_type` values `in_scope`, `out_of_scope`, or `negative`.

## Capability evidence

General capability evidence uses `capability`, `name`, and `classification`. The
classification is exactly one of `attached`, `invoked`, `completed_with_attachment`,
`absent`, or `indeterminate`. Manifest metadata and the rendered specification can
prove attachment or absence. Invocation requires trace or metric evidence. A
completed evaluation with an attached skill is `completed_with_attachment` unless
separate evidence proves invocation. Enabled MCP metadata remains `indeterminate`
because attachment is out-of-band and built-in evaluation does not call MCP tools.

## Dataset shape

The model must materialize a table with:

- `INPUT_QUERY`
- `OUTPUT` VARIANT containing:
  - `ground_truth_output`
  - `ground_truth_invocations`
  - `custom_criteria.ground_truth_ref`
  - `custom_criteria.test_type`

In-scope rows require invocations when tool metrics are selected. Boundary rows may
have an empty invocation array.

The generic coverage test verifies declared refs exactly once, boundary minimums,
and expected-tool coverage. Python execution additionally rejects missing or duplicate
`ground_truth_ref` and duplicate `INPUT_QUERY` values before starting an evaluation.
