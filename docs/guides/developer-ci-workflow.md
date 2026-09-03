# Developer and CI/CD workflow

This is the canonical executable path for building, testing, shipping, and
retiring a dbt-owned Cortex Agent. Substitute project-specific values; never
copy the example policy unchanged into production.

> **dbt is the system of record. The manifest is the contract. Layout is
> convention.**

```text
dbt models + metadata + ref() edges
                  |
                  v
        target/manifest.json
                  |
        +---------+---------+
        |                   |
        v                   v
dbt materialization   dbt-cortex-agent CLI
owns Agent DDL        owns planning/orchestration
        |                   |
        v                   +--> skill upload
CREATE / ALTER / DROP       +--> runtime and SSE
VERSION$N and routes        +--> evaluation and evidence
```

Python contains no mutating Agent DDL. A direct lifecycle command resolves the
logical Agent from a fresh manifest, checks the operation boundary, and invokes
dbt for mutation. The CLI is the reusable product interface, not a replacement
source of Agent state.

## Install one release

```bash
python -m pip install 'dbt-cortex-agent[runtime]==0.0.7'
```

```yaml
packages:
  - git: https://github.com/Jeremy-Demlow/dbt-cortex-agent.git
    revision: v0.0.7
```

The Python package coordinates files, dbt, runtime calls, and evidence. The dbt
package owns Agent DDL, immutable versions, aliases, DEFAULT, and retirement.

## Create an Agent

An Agent does not require a Semantic View. Start with a generic model:

```bash
dbt-cortex-agent agent scaffold --project-dir . --agent finance_assistant --json
dbt-cortex-agent agent scaffold --project-dir . --agent finance_assistant --apply --json
```

Add `--semantic-view-model sem_finance` only when a dbt Semantic View already
defines the governed domain. Add `--with-eval` only when representative questions
and ground truth are available. Experimental Agent specification keys remain
editable full-body YAML; the package does not expose private-preview-specific
scaffold flags.

The generated directory is a convention. Discovery comes from the parsed dbt
resource, not its path:

```text
models/agents/finance_assistant/
|-- finance_assistant.sql
|-- agent.yml
`-- skills/
    `-- README.md
```

## Validate without effects

```bash
dbt deps --project-dir .
dbt-cortex-agent doctor --project-dir . --target sandbox --json
dbt-cortex-agent manifest validate --project-dir . --target sandbox --agent finance_assistant --json
dbt compile --project-dir . --target sandbox --select finance_assistant
dbt-cortex-agent agent deploy --project-dir . --target sandbox --agent finance_assistant --allow-target sandbox --allow-database ANALYTICS_DEV --json
```

## Deploy and ask

```bash
dbt-cortex-agent agent deploy --project-dir . --target sandbox --agent finance_assistant --connection sandbox --database ANALYTICS_DEV --role AGENT_DEPLOYER --warehouse AGENT_WH --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
dbt-cortex-agent agent smoke --project-dir . --target sandbox --agent finance_assistant --question 'What can you help me answer?' --connection sandbox --database ANALYTICS_DEV --schema AGENTS --allow-target sandbox --allow-database ANALYTICS_DEV --apply
```

Human smoke output is answer-first and bounded. Use `--json` for normalized
automation output. Runtime and deployment are separately approved operations.
Use `--version 'VERSION$N'` to prove an exact immutable candidate and
`--expect-tool <tool_name>` to make routing part of the smoke contract. Raw SSE
evidence is opt-in through `--raw-events <filename>`; the package does not emit
raw protocol traffic by default.

## Understand what deployment commits

The materialization adapts dbt desired state to Snowflake's LIVE draft and
immutable version lifecycle:

```text
Agent absent
  -> deploy source A -> VERSION$1
  -> change source
  -> deploy source B -> VERSION$2
  -> roll back serving to VERSION$1
  -> unchanged deploy of source B -> no VERSION$3
  -> roll forward by routing to existing VERSION$2
```

Content identity is independent of serving DEFAULT. A rollback changes routing,
not source content, so an unchanged redeployment must not create a duplicate
version. Applied deployment reports completed durable phases such as
`version_committed`, `metadata_reconciled`, `alias_reconciled`, and
`live_reconciled`. A later failure does not erase an earlier durable phase.

## Evaluate

```bash
dbt-cortex-agent eval verify --project-dir . --target sandbox --agent finance_assistant --suite core --baseline-dir baselines --allow-target sandbox --allow-database ANALYTICS_DEV --json
dbt-cortex-agent eval verify --project-dir . --target sandbox --agent finance_assistant --suite core --baseline-dir baselines --connection sandbox --database ANALYTICS_DEV --role AGENT_EVALUATOR --warehouse AGENT_WH --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
dbt-cortex-agent eval accept-baseline <candidate.json> --baseline-dir baselines --apply --json
```

The evaluation stage must already exist. Paid verification never deploys an
Agent, and baseline acceptance is a separate policy decision.

## Promote and roll back

```bash
dbt-cortex-agent agent versions --project-dir . --target sandbox --agent finance_assistant --connection sandbox --json
dbt-cortex-agent agent promote --project-dir . --target sandbox --agent finance_assistant --version 'VERSION$2' --alias production --set-default --connection sandbox --database ANALYTICS_DEV --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
dbt-cortex-agent agent smoke --project-dir . --target sandbox --agent finance_assistant --version 'VERSION$2' --question 'What can you help me answer?' --connection sandbox --database ANALYTICS_DEV --schema AGENTS --allow-target sandbox --allow-database ANALYTICS_DEV --apply
dbt-cortex-agent agent rollback --project-dir . --target sandbox --agent finance_assistant --to-version 'VERSION$1' --alias production --set-default --connection sandbox --database ANALYTICS_DEV --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
```

Rollback moves routing and preserves newer immutable versions. Re-promoting
`VERSION$2` reuses it; it does not create `VERSION$3`.

Alias movement is not transactional. The package validates the target and
planned source state, performs the required durable operations, verifies alias
and DEFAULT postconditions, and reports partial state. After a failure, inspect
the returned state and retry the same desired route instead of assuming an
automatic rollback.

## Retire deliberately

```bash
dbt-cortex-agent agent drop --project-dir . --target sandbox --agent finance_assistant --confirm-agent ANALYTICS_DEV.AGENTS.FINANCE_ASSISTANT --connection sandbox --database ANALYTICS_DEV --allow-target sandbox --allow-database ANALYTICS_DEV --apply --json
```

Removing a dbt model never drops its Agent. The guarded command removes only the
Agent and its versions. Source files, Semantic Views, Cortex Sense contexts,
Search services, stages, skills, MCP servers, evaluations, candidates, and
baselines remain.

## CI/CD split

```text
pull request
  install -> deps -> parse -> doctor -> compile -> tests -> deploy/eval previews

protected deployment
  complete allowlists -> deploy --apply -> version-specific smoke
  -> optional paid eval verify -> retained evidence

release
  build one wheel -> offline matrices -> installed-consumer proof
  -> protected zero-state V1/V2/promote/rollback/drop proof
  -> publish that exact wheel and matching dbt tag
```

Pull requests should maximize offline confidence by default. Protected jobs
cross deployment, runtime, and paid boundaries separately and retain package
version, target, physical Agent FQN, immutable candidate version, normalized
specification hashes, completed durable phases, smoke assertions, evaluation
suite identity, and structured outcomes. Jobs for different Agents may run in
parallel; jobs addressing the same Agent need a shared concurrency key.

Main reconciles every enabled Agent to current desired state but does not need
to repeat every paid evaluation. Package release qualification is a third lane:
it builds one wheel, installs that exact artifact into clean consumer fixtures,
proves zero-state V1/V2/promotion/rollback/no-op/drop behavior, and only then
publishes the matching Python version and dbt tag.

## Authentication, authorization, and wrappers

A named Snow CLI connection determines how and who authenticates. The dbt
target determines where dbt intends to build. Repeatable allowlists determine
where this invocation is permitted to operate. Snowflake RBAC determines what
the principal can actually do. These controls are complementary.

`--database` sets the connection/default execution context. It does not assert
that every selected Agent and dependency lives in that database. Package-native
deployment carries each manifest-resolved resource database through planning and
requires every one to appear in the repeatable `--allow-database` values.

The supported connection bridge accepts `SNOWFLAKE_JWT` with account, user, and
a file-based private key, and `WORKLOAD_IDENTITY` when supplied by the execution
environment. Unsupported password, OAuth, and external-browser modes fail
closed rather than being silently treated as equivalent. Infrastructure such as
databases, schemas, roles, warehouses, stages, Semantic Views, Search services,
and evaluation stages remains owned outside this package.

No Makefile or copied Python sequencer is required. An adopter may wrap the
direct commands to inject reviewed target, role, warehouse, fleet scope,
approvals, or report retention, but the wrapper must delegate package behavior:

```text
human or CI
    +--> dbt-cortex-agent ...
    `--> adopter wrapper --> dbt-cortex-agent ...
```

If a plain package command can do it, that is product behavior. Fleet selection,
team approvals, and repository-specific reporting are adopter policy.

Exit `0` means success, `1` means completed diagnostic/quality failure, and `2`
means controlled configuration, infrastructure, or runtime failure. Agent DDL is
non-transactional: retry from inspected state rather than assuming rollback.