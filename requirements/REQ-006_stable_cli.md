# REQ-006: stable domain-oriented CLI

## Summary

Refactor the Python companion CLI into domain command handlers while preserving one stable console entry, existing command names, dry-run safety, and predictable automation behavior.

## Business context

The CLI currently combines parser construction, presentation, command routing, manifest freshness, safety checks, and domain operations in one module. That makes command behavior harder to test independently and lets expected runtime failures leak inconsistent process behavior. Duplicate connector extras and an unused role option also advertise contracts the implementation does not honor.

## Objective

Package consumers can rely on a comprehensible, automation-safe CLI whose commands remain stable while maintainers can change one domain without editing a monolithic dispatcher.

## Acceptance criteria

1. `dbt-cortex-agent` remains the only console entry and existing top-level and nested command names remain unchanged.
2. Bootstrap, manifest, skill, Agent, and eval parser/handler logic lives in domain command modules; `cli.py` owns only top-level assembly, argument parsing, and the process error boundary.
3. Exit codes are stable: `0` for success/pass, `1` for diagnostics or gate failure, and `2` for controlled configuration/runtime failure.
4. Expected connector, HTTP, JSON, filesystem, permission, and baseline-overwrite failures emit one actionable `error:` message on stderr without a traceback.
5. Dry-run remains the default for every mutation or paid operation, and execution requires explicit `--apply` where it does today.
6. Help identifies mutation and spend boundaries, includes useful descriptions for nested commands and options, and provides runnable epilog examples.
7. `--json` is available consistently for command results where structured output is appropriate; JSON mode does not mix human presentation text into stdout.
8. The unused `--role`, `SNOWFLAKE_ROLE`, and `Config.role` contract is removed rather than implying unsupported role selection.
9. Connector-backed invocation and evaluation use one `runtime` optional extra; migration guidance identifies the former `invoke` and `eval` extras.
10. The package root exports only `__version__`, and no dead or premature CLI-only public functions/types are introduced.
11. Focused and full tests, package build, import checks, and a clean wheel installation smoke from outside the repository pass without Agent commit, live mutation, or paid evaluation.

## User stories

- As an automation author, I can distinguish gate failure from controlled runtime failure by exit code and consume JSON without scraping human text.
- As a package consumer, I can identify every command that mutates state or spends evaluation credits before opting in with `--apply`.
- As a maintainer, I can modify one CLI domain without changing a monolithic dispatcher or expanding the package public API.
- As an installer, I use one connector extra for all runtime-backed commands and receive a clear migration path from the former extras.

## Dependencies

- REQ-002 dbt/Python ownership boundary.
- REQ-003 explicit bootstrap configuration.
- REQ-004 lifecycle safety and fresh-manifest behavior.
- REQ-005 dbt-rendered evaluation plan and baseline policy.

## Out of scope

- dbt macro, model, manifest, deployment, or evaluation semantic changes.
- Agent commit, alias movement, live mutation, or paid evaluation.
- Adding new lifecycle commands or changing existing command names.

## Notes

- Objective lever: separate command presentation/routing from existing domain business logic and make the top-level process contract explicit.
- Data proof: current CLI tests enumerate all command names, dry-run defaults, manifest freshness, connection gates, and eval exit behavior; package metadata exposes the duplicate connector extras.
- Assembly line: parse one stable command tree -> resolve shared config -> invoke one domain handler -> render human or JSON output -> map expected failures to stable exit codes.
- Reversible local choice: internal modules live under `dbt_cortex_agent.commands`; they are implementation details and are not re-exported from the package root.
- Verifier: substituted by full local tests, package build, clean wheel-install smoke, help/exit-code contract tests, and offline dbt parse/compile because this is a CLI layout/config slice and live mutation or paid evaluation would violate scope.
- Critic: no blocking findings remain after making baseline acceptance preview-only by default, enforcing handler exit-code bounds, and adding both invocation and evaluation migration checks for the consolidated runtime extra.
- Verification on 2026-08-04: all 117 Python tests passed; `git diff --check` and Python byte-compilation passed; `uv build` produced the v0.3.0 source distribution and wheel; the wheel installed into `/tmp/dbt-cortex-agent-wheel-smoke` and passed version, top-level help, Agent deploy help, eval run help, import, and package-root API smoke from `/tmp`. The integration consumer completed `dbt deps` and offline `dbt parse --no-partial-parse`. `dbt compile`, including a retry with dbt Core 1.11.11 and `--no-introspect`, attempted adapter authentication and failed closed on the deliberately nonexistent `/tmp/nonexistent_offline_key.p8`; no credential, live Snowflake operation, Agent commit, or paid evaluation was used. No dbt files or behavior were changed by REQ-006.