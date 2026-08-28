# REQ-028: Executable Developer and CI/CD Guide

**Status:** Complete (`0.0.6`)

## Summary

Ship executable source material for a developer-facing article that teaches the complete package workflow from creation through protected CI/CD and retirement.

## Acceptance Criteria

1. The guide explains Python/dbt ownership and pins matching PyPI `0.0.6` and dbt Git `v0.0.6` coordinates.
2. It demonstrates generic Agent scaffolding first, with Semantic View, Search, skills, MCP, evaluation, and experimental mappings as optional additions.
3. It covers doctor, manifest validation, parse, compile, deploy preview/apply, compact smoke, and controlled failure recovery.
4. It covers evaluation authoring, preview, paid verify, candidate evidence, quality gates, and separate baseline acceptance.
5. It covers version inventory, direct-version smoke, promotion, rollback, roll-forward, no-change reconciliation, and guarded retirement.
6. It provides PR, protected-main deployment, concurrency, approvals, exact-wheel qualification, and release-publishing examples without copied package mechanics.
7. It documents authentication, least privilege, allowlists, runtime/evaluation cost boundaries, non-transactional phases, and retained evidence.
8. Every package command snippet is parsed or syntax-tested against the shipped CLI; core journeys run in an installed-consumer fixture.
9. Package and adopter Cortex skills, README, CLI reference, testing guide, and article source contain no stale release or contradictory ownership claims.
10. A machine-readable evidence map links article claims to requirement criteria and offline/live proof artifacts without secrets or customer data.

## Evidence

Offline qualification on 2026-08-28 verifies documented commands, CI gates,
release preflight behavior, wheel inventory, Twine metadata, and coherent sdist
requirement/test evidence.

`TC-028-01` through `TC-028-10` in `tests/test_cases.md`.