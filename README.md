# dbt_cortex_agent

`dbt_cortex_agent` is a Snowflake-only dbt package for defining, validating,
rendering, versioning, and evaluating Snowflake Cortex Agents from dbt metadata.

Agents are dbt **exposures**, not fake relations. Semantic views and evaluation
datasets remain dbt models, while explicit macros manage the Agent lifecycle:
LIVE drafts, immutable `VERSION$N` versions, aliases, skills, MCP attachment, and
Agent-object grants.

## At a glance

| Capability | Package contract |
|---|---|
| Agent definition | Exposure with `config.meta.cortex_agent` |
| Eval definition | Table model with `config.meta.cortex_eval` |
| Dependencies | Exposure `depends_on`, model `ref()`, manifest resolution |
| Deployment | Explicit `cortex_agent__deploy`; dry-run by default |
| Versioning | Spec/skill hashes, LIVE commit, aliases, no-change skip |
| Evaluation | Native eval config/start/poll/results/threshold macros |
| Safety | Mutations restricted to `cortex_agent_deploy_target` |
| dbt | `>=1.9,<2.0`; dbt Core + Snowflake is authoritative |

## End-to-end flow

```text
AUTHOR [consumer dbt project]
  Agent exposure + semantic models + eval table + optional skills
                    |
                    v
          dbt parse / resolved graph
                    |
         +----------+-----------+
         |                      |
         v                      v
  Package macros [P]     target/manifest.json
  validate + render             |
         |                      v
         |              Copyable tooling [T]
         |              scope + orchestrate
         +----------+-----------+
                    |
       +------------+-------------+
       |                          |
       v                          v
  CANONICAL LANE             NATIVE-EVAL LANE
  upload skills first        filtered *_EVAL Agent
  hash spec + skills         materialize ground truth
  commit VERSION$N           run Agent Evaluation
  assign alias               threshold + baseline gate
       |
       +--> separate grants, promotion, rollback, MCP, and smoke

[P] installed dbt package   [T] optional copied tooling   [R] reference only
```

See the [detailed end-to-end flow](docs/concepts/end-to-end-flow.md) for ownership,
failure boundaries, versioning, evaluation, and CI behavior.

## Installation status

The package is developed in `agentmanagementdbt` and released to the private
`Jeremy-Demlow/dbt-cortex-agent` repository. During monorepo development, use the
local package path:

```yaml
# packages.yml in the consuming dbt project
packages:
  - local: ../packages/dbt_cortex_agent
```

Then install it:

```bash
dbt deps
```

For the standalone repository, pin the immutable `v0.2.0` Git revision; never use
an unpinned branch. See [installation](docs/getting-started/installation.md).

## First Agent

For a complete minimal consumer that is compiled and contract-tested independently,
start with the [`starter_project`](examples/starter_project/README.md). The inline
example below is the same adoption shape in condensed form.

Create an exposure in `models/agents/orders_assistant/agent.yml`:

```yaml
version: 2

exposures:
  - name: orders_assistant
    label: Orders Assistant
    type: application
    maturity: medium
    owner:
      name: analytics
      email: analytics@example.com
    depends_on:
      - ref('sem_orders')
    config:
      meta:
        cortex_agent:
          enabled: true
          snowflake_name: ORDERS_ASSISTANT
          naming:
            sandbox: ORDERS_ASSISTANT_SANDBOX
            prod: ORDERS_ASSISTANT
          access:
            usage_roles: [ORDERS_AGENT_USER]
          model:
            orchestration: claude-sonnet-4-5
          orchestration:
            budget: {seconds: 60, tokens: 16000}
          instructions:
            orchestration: Use OrdersAnalytics for governed order questions.
            response: Answer concisely and include the requested time scope.
          sample_questions:
            - What was order revenue last month?
          tools:
            - name: OrdersAnalytics
              type: cortex_analyst_text_to_sql
              semantic_view_model: sem_orders
              warehouse: "{{ target.warehouse }}"
              description: >
                Analyzes governed order revenue and volume. Use for order trends
                and period comparisons. Not for customer-support policy.
```

The exposure `depends_on` creates dbt lineage. `semantic_view_model` is resolved
against the manifest and must identify a `semantic_view` model.

## Validate, render, and dry-run

```bash
dbt parse

dbt run-operation cortex_agent__validate \
  --args '{"agent_name":"orders_assistant","projection":"canonical"}'

dbt run-operation cortex_agent__render_spec \
  --args '{"agent_name":"orders_assistant","projection":"canonical"}'

dbt run-operation cortex_agent__deploy \
  --args '{"agent_name":"orders_assistant","projection":"canonical","dry_run":true}'
```

`cortex_agent__deploy` is non-mutating by default. A live deployment additionally
requires the active target to equal `cortex_agent_deploy_target`.

## Deploy and manage versions

```bash
dbt run-operation cortex_agent__deploy --target sandbox \
  --args '{"agent_name":"orders_assistant","projection":"canonical","dry_run":false}'

dbt run-operation cortex_agent__promote_alias --target sandbox \
  --args '{"agent_name":"orders_assistant","from_alias":"validated","to_alias":"production","dry_run":true}'

dbt run-operation cortex_agent__rollback_alias --target sandbox \
  --args '{"agent_name":"orders_assistant","alias":"production","to_version":"VERSION$2","dry_run":true}'
```

Deployment compares the final spec hash and staged-skill hash with the current
version comment. Unchanged deployments skip version churn. See
[lifecycle and versioning](docs/concepts/lifecycle-and-versioning.md).

## Canonical versus native-eval

The canonical projection represents intended Agent behavior. The `native_eval`
projection excludes capabilities unsupported by built-in Cortex Agent Evaluation,
including skills, MCP connectors, and explicitly unsupported tools/capabilities.
Both projections come from one exposure. See
[canonical versus native-eval](docs/concepts/canonical-vs-native-eval.md).

## Skills, evaluations, access, MCP, and CI

- [Skills](docs/guides/skills.md)
- [Evaluations](docs/guides/evaluations.md)
- [Access control](docs/guides/access-control.md)
- [MCP connectors](docs/guides/mcp.md)
- [CI adoption](docs/guides/ci.md)

Skills and the advanced client-side evaluation gate use optional copyable tooling
from the containing repository. Those Python scripts and Make targets are not
installed by this dbt package.

## Reference

- [Agent metadata](docs/reference/agent-metadata.md)
- [Eval metadata and dataset shape](docs/reference/eval-metadata.md)
- [Public macros](docs/reference/macros.md)
- [Variables](docs/reference/variables.md)
- [Compatibility](docs/reference/compatibility.md)
- [Detailed end-to-end flow](docs/concepts/end-to-end-flow.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Upgrade policy](UPGRADING.md)
- [Changelog](CHANGELOG.md)

## Important limitations

- Snowflake is the only supported execution adapter.
- Agent exposures are deployed through explicit macros, not `dbt run`.
- Package macros called from model SQL must be package-qualified.
- Property-file Jinja cannot call custom macros; use `target`, `var`, and
  `env_var` there.
- `cortex_eval__render_config` may query the materialized dataset and Snowflake
  dataset inventory; it is not an unconditional offline render.
- Package-native evaluation gates thresholds. Retry artifacts, accepted-baseline
  comparison, and state-scoped CI are optional framework tooling.

## License

Apache License 2.0. See [LICENSE](LICENSE).
