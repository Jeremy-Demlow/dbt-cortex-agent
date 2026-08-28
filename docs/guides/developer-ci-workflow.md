# Developer and CI/CD workflow

This is the executable source path for building, testing, shipping, and retiring
a dbt-owned Cortex Agent. Substitute project-specific values; never copy the
example policy unchanged into production.

## Install one release

```bash
python -m pip install 'dbt-cortex-agent[runtime]==0.0.6'
```

```yaml
packages:
  - git: https://github.com/Jeremy-Demlow/dbt-cortex-agent.git
    revision: v0.0.6
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

Exit `0` means success, `1` means completed diagnostic/quality failure, and `2`
means controlled configuration, infrastructure, or runtime failure. Agent DDL is
non-transactional: retry from inspected state rather than assuming rollback.