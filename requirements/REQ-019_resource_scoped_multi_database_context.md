# REQ-019: Resource-Scoped Multi-Database Context

**Status:** Implemented offline; controlled live proof pending

## Summary

Support Cortex Agents, skills, and evaluations whose dbt-resolved resources live
in multiple approved Snowflake databases. Resource identity comes from the
selected manifest node or signed evaluation plan, never from a repository-wide
"current database" assumption.

## Objective

A consumer can use one target-resolved dbt manifest containing Agents and related
resources in different databases without weakening explicit connection, target,
database-allowlist, runtime, mutation, or spend controls.

## Identity Contract

```text
[target-resolved manifest]
          |
          v
[select Agent or eval suite]
          |
          v
[database + schema + object + physical FQN]
          |
          +--> [skill stage FQNs]
          +--> [eval table / stage / dataset / result identities]
          |
          v
[validate every resource database against the allowlist]
          |
     approved -> execute
     mismatch -> stop before connection or mutation
```

One package command consumes one dbt target and its fresh manifest. Coordinating
multiple dbt targets is an adopter/CI responsibility.

## Acceptance Criteria

1. Multi-database manifests enumerate Agents without requiring all project models
   to resolve to one database.
2. Agent selection retains logical name, unique ID, database, schema, object name,
   and physical FQN.
3. Agent smoke invokes the selected manifest physical identity rather than an
   ambient CLI database/schema.
4. Skill plans validate every stage database and may span multiple approved
   databases; all safety validation completes before the first upload.
5. Mutation guards validate both the approved dbt target and the actual database
   of each relation or object being changed.
6. Eval plans sign distinct Agent, table, stage, dataset/result, target, role, and
   warehouse identities. Cross-database resources are explicit rather than
   inferred from `target.database`.
7. A changed signed identity contract increments the eval-plan schema and never
   silently reinterprets old candidates or baselines.
8. Candidate, diagnostic, comparison, gate, and baseline paths cannot collide for
   same-named physical Agents in different targets/databases.
9. Every resource database is checked against repeatable `--allow-database` and
   dbt allowlists before connector construction, mutation, runtime, or spend.
10. Single-database projects preserve current command behavior where identity is
    unambiguous.
11. Unit/macro fixtures cover unrelated databases, two Agents in two databases,
    repeated object names, multi-database stages, partial allowlists, and Agent DB
    A with eval table DB B and stage DB C.
12. Installed-wheel verification proves manifest, skill-plan/upload preview,
    Agent-smoke preview, and eval preview behavior without credentials.
13. A protected package-owned workflow installs the exact built wheel and proves
    two same-named Agent objects in separate databases, independent versions and
    aliases, runtime smoke, and no-change reconciliation.
14. The live workflow never runs for pull requests, uses dedicated proof objects,
    retains only sanitized attestation, and performs idempotent cleanup.
15. PyPI publication consumes the same wheel artifact and requires its live
    proof; manual build-only validation remains available. The GitHub release
    event that starts qualification is not itself gated.

## Out of Scope

- Implicitly parsing or executing multiple dbt targets in one package command.
- Discovering roles, warehouses, GitHub environments, or credentials from Agent
  model metadata.
- Automatic production promotion or baseline acceptance.

## Verification

- Full package unit and macro suites.
- dbt integration fixtures and credential-free installed-wheel verification.
- Python compile, distribution build, Twine check, wheel inventory, public-content
  policy, secret policy, and diff checks.
- Controlled non-production proof is required before broad public support claims.

## Live Proof Contract

```text
[exact wheel + matching dbt package commit]
                    |
                    v
 [dedicated A/B proof databases + least-privilege role]
                    |
        +-----------+-----------+
        v                       v
 [A.AGENTS.SHARED]       [B.AGENTS.SHARED]
        |                       |
        +-----------+-----------+
                    v
 [version / aliases / smoke / no-change proof]
                    |
                    v
 [sanitized attestation + unconditional cleanup]
```

The default live proof excludes paid evaluation. It must render and validate the
schema-v2 evaluation plan; paid `--apply` remains a separately approved boundary.

## Verification Record

- Package tests: 194 passed.
- Live-verifier/workflow contracts: 20 passed; explicit three-database dbt parse passed.
- Python compile, sdist/wheel build, and Twine checks passed in the offline implementation pass.
- No Snowflake mutation, runtime invocation, paid evaluation, baseline movement,
  commit, or push occurred in the offline implementation pass.