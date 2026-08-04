# REQ-003: Explicit bootstrap configuration

## Summary

Remove repository-owner and sandbox assumptions from the Python bootstrap so adopters explicitly choose package provenance and deployment boundaries.

## Business context

Bootstrap output becomes part of a consumer's dependency and mutation-safety contract. Personal repository URLs, implicit targets, empty database allowlists, and conventional schemas must not be installed as if they were adopter decisions.

## Objective

Consumers initialize `dbt_cortex_agent` without inheriting unapproved package sources or deployment settings.

## Acceptance criteria

1. The default package revision is derived as `v{dbt_cortex_agent.__version__}` and no personal Git URL is a runtime default.
2. Init requires `--package-source` when no existing `dbt_cortex_agent` dependency can be identified; an identified existing dependency is left byte-for-byte unchanged.
3. Existing package detection accepts an exact requested Git source, the exact `dbt_cortex_agent` package coordinate, or an exact local package directory name, and does not identify arbitrary Git forks from repository suffix alone.
4. Init adds deployment safety vars only when `--target` is explicitly supplied. A new safety configuration requires at least one adopter-provided `--allow-database`; repeatable `--allow-target` values are supported and the explicit target is included automatically.
5. Init accepts `--agent-schema` and `--eval-schema` and adds those vars only when explicitly supplied.
6. Preview is non-mutating and describes narrowly appended package and var snippets; apply appends only missing top-level package/vars while preserving comments, unrelated fields, and every existing value.
7. Doctor explains missing target or incomplete allowlists without selecting `sandbox` or `dbt_focus`.
8. Focused tests, the full Python package test suite, and a Python package build pass when the local environment supports them.

## User stories

- As a package consumer, I explicitly select the dependency source instead of inheriting a maintainer's repository URL.
- As a platform owner, I explicitly name deploy targets and allowed databases before bootstrap adds mutation-safety configuration.
- As an adopter with an established dbt project, I can preview and apply bootstrap changes without losing comments or existing configuration.

## Dependencies

- The v0.3.0 Python companion established by REQ-002.
- Existing dbt deployment safety variables and doctor diagnostics.

## Out of scope

- Changing macro-level defaults or Agent/evaluation runtime behavior.
- Rewriting existing consumer package declarations or vars.
- Running live deployments or paid evaluations.
- Defining `AGENTS` or `EVAL` as mandatory schema conventions.

## Notes

- This slice uses the canonical `--package-source` and `--revision` CLI names; the old `--git-url` option is removed rather than retained as an undocumented alias.
- Reversible, slice-local choice: `--package-source` represents a Git dependency source. Existing local and package-coordinate dependencies are recognized but new local/package-coordinate declarations remain manual.
- Verifier: focused and full pytest plus Python source/wheel build. No Snowflake mutation or paid evaluation is needed for this bootstrap-only slice.
- Verification on 2026-08-04: 30 focused bootstrap/doctor/CLI tests passed; all 72 Python package tests passed; `uv build` produced the v0.3.0 source distribution and wheel; `git diff --check` passed. dbt parse/compile were not run because this slice changes no dbt model, macro, SQL, eval, or deploy behavior.