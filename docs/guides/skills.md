# Skills

Skills are declared under `capabilities.skills` and rendered only in the canonical
projection.

```yaml
capabilities:
  skills:
    - name: order_summary
      description: Summarize order anomalies.
      source:
        type: stage
        path: "@{{ target.database }}.{{ var('cortex_agent_schema','AGENTS') }}.{{ var('cortex_agent_skill_stage','SKILL_STAGE') }}/agents/orders_assistant/order_summary"
```

Property-file Jinja cannot call custom package macros. Build paths with `target`,
`var`, or `env_var`.

## Local layout

- Private: `models/agents/<agent>/skills/<skill>/SKILL.md`
- Shared: `skills/library/<skill>/SKILL.md`

Exclude colocated skill folders from dbt parsing:

```text
models/agents/*/skills/**
```

## Deployment boundary

The package validates staged skill readiness and includes staged file metadata in
Agent idempotency. Local file upload uses optional copyable Python/Snow CLI tooling
from the framework repository; it is not installed by this dbt package.

In the reference framework, use the unified flow:

```bash
make dbt-focus-agent-deploy AGENT=orders_assistant DRY_RUN=1
make dbt-focus-agent-deploy AGENT=orders_assistant
make dbt-focus-skill-smoke AGENT=orders_assistant
```

The orchestrator reparses the current project, resolves only selected Agent skills,
deduplicates shared stage paths, validates the complete upload plan, uploads every
skill, and only then calls the existing canonical Agent deploy macro. Any parse,
plan, or upload failure prevents Agent mutation. Smoke is subsequent because it is
a live behavioral check rather than a deployment prerequisite.

Stage-backed skills are readiness-checked. Other source types are not currently
uploaded or remotely validated by the framework tooling.

Built-in native Agent Evaluation excludes skills. Verify skill selection with a
separate smoke/integration test.
