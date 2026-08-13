# REQ-018: Sanitized evaluation failure diagnostics

**Status:** Complete

## Problem

Native evaluation failures occur before candidate results are written. The
package previously raised a terminal error containing status details but
persisted no machine-readable evidence for the actual retry run name, request
identifier, inference identifier, or platform error code. Consumers either
lost those identifiers or had to retain unsafe raw evaluation output.

## Decision

On terminal evaluation failure, write a whitelist-only diagnostic artifact
under:

```text
<artifact_dir>/diagnostics/<agent>/<suite>/<run_name>.json
```

The artifact contains only:

- logical Agent and suite names;
- the actual run name, including retry suffix;
- terminal status;
- request and inference identifiers when Snowflake returns them;
- normalized error category and error code.

Raw status details, prompts, responses, tool payloads, configuration paths,
connection metadata, and arbitrary Snowflake result columns are excluded.

## Acceptance criteria

1. Polling reads identifiers by explicit column name and ignores arbitrary
   extra columns.
2. A terminal failure writes one contained-path diagnostic before raising.
3. Missing request or inference identifiers produce empty arrays rather than
   fabricated values.
4. Retry failures use the final retry run name.
5. Preview mode remains connection-free and writes no diagnostic.
6. Tests prove private status text and unknown result fields are absent from
   the artifact.

## Verification

- `tests/test_eval.py::test_poll_whitelists_native_diagnostic_identifiers`
- `tests/test_eval.py::test_terminal_failure_writes_whitelist_only_diagnostic`
- Full package suite: `337 passed` before requirement documentation was added.