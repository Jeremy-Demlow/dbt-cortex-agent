# End-to-end architecture flow

The framework has three ownership boundaries:

- **[P] Package:** installed from `dbt_cortex_agent`; owns metadata validation,
  deterministic rendering, Agent lifecycle macros, grants, and package-native evals.
- **[T] Tooling:** optional Python, Snow CLI, Make, and CI assets copied and adapted
  from the full framework repository.
- **[R] Reference:** the ski-resort project, data generation, baselines, and examples
  that demonstrate a complete implementation but are not package dependencies.

## Complete control plane

```text
AUTHORING [consumer project]
┌─────────────────────────────────────────────────────────────────────┐
│ Agent exposure                                                      │
│   config.meta.cortex_agent                                          │
│   depends_on -> semantic-view models                                │
│                                                                     │
│ Eval table model                                                    │
│   config.meta.cortex_eval                                           │
│   INPUT_QUERY + OUTPUT VARIANT                                      │
│                                                                     │
│ Optional skills                                                     │
│   private: models/agents/<agent>/skills/<skill>/SKILL.md            │
│   shared:  skills/library/<skill>/SKILL.md                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ dbt deps + dbt parse
                               v
DBT RESOLUTION [P]
┌─────────────────────────────────────────────────────────────────────┐
│ Resolved graph: exposures, models, refs, target relation names      │
│                                                                     │
│ Package macros consume the in-memory graph.                         │
│ Python tooling consumes only target/manifest.json.                  │
└───────────────┬──────────────────────────────┬──────────────────────┘
                │                              │
                │ canonical                    │ native_eval
                v                              v
CANONICAL DEPLOYMENT [T]+[P]           EVALUATION LANE [T]+[P]
┌───────────────────────────────┐      ┌───────────────────────────────┐
│ deploy_agent.py [T]           │      │ agent_gate.py [T]             │
│  1. fresh dbt parse           │      │  1. discover selected suites  │
│  2. selected skill plan       │      │  2. deploy native_eval Agent  │
│  3. deduplicated upload       │      │  3. run/test eval table       │
│  4. canonical deploy macro    │      │  4. start/poll evaluation     │
└──────────────┬────────────────┘      │  5. compare accepted baseline │
               │                       └───────────────┬───────────────┘
               v                                       │
┌───────────────────────────────┐                       v
│ Skill stage [T]               │      ┌───────────────────────────────┐
│ Snow CLI recursive upload     │      │ Native-eval Agent             │
│ SNOWFLAKE_SSE internal stage  │      │ - separate suffixed object    │
└──────────────┬────────────────┘      │ - no skills or MCP            │
               │                       │ - unsupported tools excluded  │
               v                       └───────────────┬───────────────┘
┌───────────────────────────────┐                      │
│ cortex_agent__deploy [P]      │                      v
│ validate + render             │      ┌───────────────────────────────┐
│ verify staged SKILL.md        │      │ Snowflake Agent Evaluation    │
│ compare spec + skill hashes   │      │ START -> poll -> result rows  │
│ modify LIVE draft             │      │ -> candidate JSON artifact    │
│ COMMIT VERSION$N              │      │ -> thresholds + regression    │
│ assign deploy alias           │      └───────────────────────────────┘
│ recreate LIVE                 │
│ optionally attach MCP         │
└──────────────┬────────────────┘
               │
               ├── grant Agent usage [P], separate DDL
               ├── promote or rollback alias [P], separate operation
               └── skill-selection smoke [T], subsequent live verification
```

## Why the manifest is central

dbt is the system of record. The Agent is an exposure, semantic views and eval
datasets are models, and references create the dependency graph. Package macros
read dbt's resolved graph directly. Optional Python tooling reads the generated
manifest and does not reparse source YAML or maintain a second configuration model.

This boundary makes database/schema/alias resolution, Agent selection, eval dataset
FQNs, and skill declarations consistent across package macros and CI tooling.

## Canonical deployment ordering

The recommended copied orchestrator is fail-closed:

1. Produce a fresh manifest.
2. Select enabled Agent exposures.
3. Resolve and validate the complete skill upload plan.
4. Deduplicate identical shared stage paths.
5. Upload every selected skill.
6. Invoke the package canonical deployment macro only after all uploads succeed.

The package then independently verifies staged `SKILL.md` files before mutation.
It hashes the final Agent specification and staged skill metadata. An unchanged
deployment skips version churn. A changed deployment updates LIVE, commits an
immutable `VERSION$N`, assigns the deploy alias, and recreates LIVE from the last
version. MCP attachment and Agent-object grants are separate typed DDL operations.

## Native-eval projection

Built-in Cortex Agent Evaluation does not support every canonical capability. The
framework therefore renders a separate evaluator-compatible Agent from the same
exposure instead of weakening intended production behavior.

The native-eval projection:

- uses a suffixed Agent name,
- excludes all skills and MCP connectors,
- excludes tools and code execution explicitly marked unsupported,
- preserves supported tools, instructions, model, and budget.

Package-native eval macros can start, poll, collect, and threshold-gate an evaluation.
The optional Python bridge adds retry, durable JSON results, accepted-baseline
comparison, suite-signature checks, and state-scoped CI.

## CI failure posture

Cheap package, compile, contract, and render checks run before spend-bearing work.
State-based CI combines changed paths, dbt graph changes, and manifest ownership to
select affected Agents. Missing base state or a contradiction between relevant
changes and an empty selection widens to every enabled Agent. Uncertainty can cost
more, but it cannot silently skip correctness validation.

Skill smoke and paid Agent Evaluation remain explicit live steps. They are not
required to verify documentation, package structure, or deterministic rendering.

## What the starter proves

The package-local [`starter_project`](../../examples/starter_project/README.md) is
the smallest independent consumer. It proves package installation, semantic-view
compilation, Agent/eval metadata resolution, package-qualified macros/tests, and
deterministic canonical/native-eval rendering.

It intentionally does not prove live Agent deployment, staged skills, MCP, smoke,
or paid evaluation. Those advanced paths are demonstrated by the full reference
framework and require explicit Snowflake mutation/spend approval.
