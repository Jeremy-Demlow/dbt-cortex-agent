# Eval metadata reference

Eval metadata lives at `models[].config.meta.cortex_eval` on a table model.

## Required fields

| Field | Type | Contract |
|---|---|---|
| `name` | string | Suite name |
| `agent` | string | Enabled Agent exposure name |
| `projection` | string | Use `canonical` or `native_eval` |
| `metrics` | non-empty list | Built-in names or custom metric objects |
| `questions` | non-empty list | Suite contract rows |

## Optional fields and complete nested inventory

| Field path | Type | Required | Default / consumer |
|---|---|---:|---|
| `description` | string | No | `Automated evaluation` |
| `metrics[]` | string/object | Yes | At least one entry |
| `metrics[].name` | string | Custom metric only | Custom metric identifier |
| `metrics[].prompt` | string | Custom metric only | Judge prompt |
| `metrics[].score_ranges` | mapping | No | Passed through to native evaluation |
| `thresholds.<metric>` | number | No | Package-native hard floor |
| `regression_tolerances.<metric>` | number | No | Optional Python baseline comparison only |
| `questions[]` | object | Yes | At least one entry |
| `questions[].id` | string | Yes | Question identifier |
| `questions[].test_type` | string | Recommended | `in_scope`, `out_of_scope`, or `negative` |
| `questions[].expected_tools[]` | string | No | Must exist in selected projection |
| `questions[].ground_truth_ref` | string | Yes | Must map to exactly one live dataset row |

Custom metrics require `name` and `prompt`. `thresholds` are used by package-native
gating. `regression_tolerances` are consumed by optional framework comparison tooling.

Each question requires `id` and `ground_truth_ref`; `expected_tools` must exist in
the selected rendered projection. Use `test_type` values `in_scope`,
`out_of_scope`, or `negative`.

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
and expected-tool coverage. It does not currently reject every possible undeclared
extra dataset row; use a uniqueness test on `INPUT_QUERY` and keep SQL/YAML changes
reviewed together.
