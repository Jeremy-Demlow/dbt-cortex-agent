# REQ-024: Generic Agent Scaffold and Developer Journey

**Status:** Complete (`0.0.6`)

## Summary

Provide a preview-first scaffold for a valid, editable dbt-owned Agent. An Agent does not require a Semantic View. Analyst, evaluation, skills, Search, MCP, and experimental features are optional capabilities.

## Acceptance Criteria

1. `agent scaffold --agent <name>` plans a deterministic generic Agent model, metadata file, and skill directory without requiring a Semantic View or Snowflake connection.
2. `--semantic-view-model <model>` optionally adds an Analyst tool and explicit dbt dependency; dbt parse/compile then proves the model resolves uniquely and is materialized as a Semantic View before deployment.
3. `--with-eval` optionally adds a deterministic editable evaluation model and suite skeleton targeting the same Agent.
4. Generated instructions are domain-neutral placeholders and do not invent tables, joins, metrics, business rules, roles, databases, or warehouses.
5. The full-body contract accepts and preserves an arbitrary mapping under `experimental`; no private-preview key receives a package-specific CLI option in `0.0.6`.
6. A model containing `EnableCortexSense` and `FallbackWarehouse` round-trips through parse, render, deploy preview, content hashing, and unchanged reconciliation without removal or reinterpretation.
7. The scaffold validates all paths and collisions before writing, treats identical files as no-ops, and fails closed on differing files without a force mode.
8. Preview performs no writes; apply reports every created and unchanged path in stable human and JSON output.
9. Bare, Analyst-backed, and experimental-passthrough fixtures compile using the installed wheel and matching dbt package tag outside the source checkout.
10. Package documentation and the Cortex project skill teach the same capability-neutral scaffold and explicit approval boundaries.

## Non-Goals

- Creating or discovering a Cortex Sense context.
- Cortex Sense-specific CLI flags or generated prompts while the feature is private preview.
- A generic business-domain prompt generator.
- Creating a new dbt project.

## Evidence

Offline qualification on 2026-08-28 verifies generic Agent-only scaffolds,
optional Analyst/evaluation assets, collision refusal, and installed-wheel
consumer workflows under dbt 1.10 and 1.11.

`TC-024-01` through `TC-024-10` in `tests/test_cases.md`.