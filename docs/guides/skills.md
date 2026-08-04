# Skills

Skills are declared under `capabilities.skills`, discovered through the dbt
manifest, and included only in the canonical Agent projection.

```yaml
capabilities:
  skills:
    - name: order_summary
      source:
        type: stage
        path: "@{{ target.database }}.{{ var('cortex_agent_schema','AGENTS') }}.{{ var('cortex_agent_skill_stage','SKILL_STAGE') }}/agents/orders_assistant/order_summary"
```

Property-file Jinja may use `target`, `var`, and `env_var`; it cannot call package
macros. The declared stage suffix must mirror local layout:

- private: `models/agents/<agent>/skills/<skill>/SKILL.md`
- shared: `skills/library/<skill>/SKILL.md`

Exclude private skill directories from dbt model parsing with the project's
`.dbtignore`.

## Plan, upload, deploy, smoke

Every manifest-dependent command reparses before reading the manifest.

```bash
dbt-cortex-agent skill plan --project-dir . --target sandbox \
  --agent orders_assistant --json
dbt-cortex-agent skill upload --project-dir . --target sandbox \
  --agent orders_assistant --json
```

Both commands are non-mutating as shown. To upload, repeat `skill upload` with an
explicit connection/database, both allowlists, and `--apply`. The CLI validates
the complete plan, deduplicates shared stage paths, and invokes Snow CLI only
after planning succeeds. A failure prevents subsequent deployment.

After upload, run `agent deploy`; mutating canonical deploy independently checks
that each declared stage-backed skill contains `SKILL.md` and includes staged
file state in the idempotency hash.

Skill smoke is a subsequent live runtime check, not a deploy prerequisite:

```bash
dbt-cortex-agent skill smoke --project-dir . --target sandbox \
  --agent orders_assistant --database ANALYTICS_DEV --schema AGENTS
```

The preview maps logical exposures to physical Agent names. A live call requires
the `runtime` extra, explicit `--connection`, both allowlists, and `--apply`.
`--agent-object` is allowed only for exactly one selected logical Agent.

Built-in native Agent Evaluation excludes skills. Verify skill selection with
smoke or another explicit integration test.