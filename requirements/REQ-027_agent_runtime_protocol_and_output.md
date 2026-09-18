# REQ-027: Agent Runtime Protocol and Compact Output

**Status:** In progress; historical `0.0.6` replay retained, current protocol corpus/schema gaps in `tests/requirement_evidence.json`.

## Summary

Turn Cortex Agent SSE into a small typed result and useful CLI output instead of printing large raw tool payloads. Keep raw evidence available only through an explicit bounded path.

## Acceptance Criteria

1. Runtime handling separates SSE framing, event normalization, result accumulation, and presentation into pure testable components.
2. SSE framing supports multiline data, blank-line event boundaries, `[DONE]`, and a final unterminated failure.
3. Malformed JSON, explicit Agent errors, HTTP failures, timeouts, and unknown required protocol states fail closed with categorized errors.
4. Normalization captures answer text, tools, SQL, bounded result summaries, charts, annotations, metadata, errors, duration, and version provenance.
5. Default human output leads with the answer and prints only compact bounded summaries.
6. `--json` emits a stable normalized result without raw events or unbounded result sets by default.
7. Raw event retention is explicit, bounded, and preferably written to a collision-safe contained artifact rather than stdout.
8. Tool-use assertions rely on exact normalized evidence and do not infer invocation from attachment or status prose.
9. Recorded protocol fixtures cover tool-less answers, multiple tools/results, charts, annotations, malformed streams, and protocol additions.
10. The base runtime adds no pandas or async HTTP dependency; a future async API must reuse the same normalization contract.

## Evidence

Offline qualification on 2026-08-28 verifies SSE framing and normalization,
recorded current-protocol replay, explicit bounded collision-safe raw-event
artifacts, compact output, exact tool evidence, and additive event tolerance.
Live runtime replay returned `$405.75` from both databases and from exact
immutable version selectors.

`TC-027-01` through `TC-027-10` in `tests/test_cases.md`.