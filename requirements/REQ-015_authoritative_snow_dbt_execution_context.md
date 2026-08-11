# REQ-015: authoritative Snow/dbt execution context

## Status

Complete.

## Summary

An explicitly selected Snow CLI connection is the authoritative execution identity for every dbt,
Snow CLI, and Python connector operation performed by one `dbt-cortex-agent` command.

## Objective

Prevent split-brain execution where dbt parses or renders against ambient profile credentials while
stage, runtime, or evaluation operations use the explicitly selected Snow CLI connection.

## Acceptance criteria

1. `--connection NAME` is resolved once, before the command handler runs, and supplies the dbt child
   process account, user, authentication, database, role, and warehouse settings.
2. Explicit `--database` and `--warehouse` values override matching connection defaults for both dbt
   and runtime validation; `--target` supplies `DBT_TARGET`.
3. The resolved environment is passed to every package-owned `dbt deps`, `dbt parse`, and
   `dbt run-operation` subprocess without mutating global `os.environ`.
4. Snow CLI stage commands and Python connector calls continue to use the same named connection.
5. The initial bridge supports file-based key-pair authentication. Missing connections, required
   fields, key paths, or unsupported authentication fail before dbt, Snowflake mutation, runtime, or
   paid evaluation begins.
6. Private keys, passphrases, passwords, and tokens are never written to disk or emitted in argv,
   logs, JSON, errors, or artifacts.
7. Commands without an explicit connection retain credential-free/offline profile behavior; an
   environment-only connection name never satisfies an apply boundary.
8. Unit and installed-wheel tests prove connection resolution, override precedence, redaction,
   external-working-directory execution, and environment propagation through manifest, Agent,
   skill, and evaluation paths.

## Out of scope

- Password, OAuth, browser, token, workload identity, or inline private-key authentication bridges.
- Persisting generated dbt profiles or credentials.
- Agent mutation, runtime invocation, paid evaluation, baseline acceptance, or release publication.

## Dependencies

- REQ-004 lifecycle safety and fresh-manifest behavior.
- REQ-006 stable domain-oriented CLI.
- REQ-014 installed-wheel single-Agent verifier.

## Verification record

- Maker record (2026-08-11): added in-memory Snow CLI connection resolution, explicit option provenance, file-based `SNOWFLAKE_JWT` validation, masked-secret rejection, and child-environment propagation through all package-owned dbt subprocesses.
- Critic record (2026-08-11): found masked passphrase forwarding, ambient override precedence, incomplete authenticator validation, and missing coverage. The implementation now takes passphrases only from the inherited child environment, tracks explicit overrides, rejects conflicting authentication, and expands the requirement/test contracts.
- Verifier record (2026-08-11): 334 package tests passed; source distribution and wheel built; Twine validated both artifacts; the exact wheel completed the isolated dbt 1.11 Agent-only and Agent-plus-optional-eval verifier from an external workspace. No Snowflake mutation, runtime, paid evaluation, baseline movement, tag, or release occurred.