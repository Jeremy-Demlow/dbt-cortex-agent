# Changelog

This project had no public beta or stable release before `0.0.1`. Earlier Git
history records design experiments, not supported package versions.

## Unreleased

- No changes yet.

## 0.0.1 — 2026-08-18

- Added a Snowflake-only `cortex_agent` custom materialization. The dbt model
  body is the Agent specification; `dbt compile` validates it and `dbt build`
  owns creation, immutable versions, aliases, profile, and comments.
- Added manifest-driven skill planning, upload to an existing infrastructure-
  managed stage, and live skill smoke proof.
- Added optional evaluation planning, paid execution, polling, result artifacts,
  threshold and baseline gates, and explicit baseline acceptance.
- Added the fixed synthetic Orders starter and installed-wheel/dbt compatibility
  verification for dbt Core 1.10 and 1.11.
