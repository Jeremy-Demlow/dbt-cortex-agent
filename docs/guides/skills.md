# Skills

The native Agent model body declares top-level `skills`. Local upload planning
requires matching declarations in `config.meta.cortex_agent.skills`, which dbt
resolves into the manifest during parse. `capabilities.skills` is not supported.
The CLI never substitutes compiled YAML for this explicit upload contract:
fresh `dbt parse` normally does not populate `compiled_code`.

Declare local uploads in model property YAML (for example `agent.yml`):

```yaml
version: 2
models:
  - name: orders_assistant
    config:
      meta:
        cortex_agent:
          skills:
            - name: order_summary
              source:
                type: stage
                path: "@{{ target.database }}.AGENTS.SKILL_STAGE/agents/orders_assistant/order_summary"
```

Include the matching native declaration in the Agent model body:

```yaml
skills:
  - name: order_summary
    source:
      type: stage
      path: "@{{ target.database }}.AGENTS.SKILL_STAGE/agents/orders_assistant/order_summary"
```

Property-file Jinja may use `target`, `var`, and `env_var`; it cannot call package
macros. The declared stage suffix must mirror local layout:

- private: `models/agents/<agent>/skills/<skill>/SKILL.md`
- shared: `skills/library/<skill>/SKILL.md`

Exclude private skill directories from dbt model parsing with the project's
`.dbtignore`.

The native model remains the deployment specification authority. Metadata is
the local upload and skill-smoke discovery contract, not a second renderer.
Readable, non-Jinja model YAML/JSON in the manifest is checked against metadata
by skill name, source type, and path. Missing, extra, duplicate, malformed, or
unresolved declarations fail before upload. Stage identifiers are normalized;
folder suffixes remain case-sensitive during comparison. Non-stage declarations
are validated but are not uploaded or included in stage-skill smoke.

Without compiled evidence, Python does not evaluate Jinja. Detectable skill
references without resolved nonempty metadata fail rather than plan nothing.
This conservative detection uses the text `skills`, so uncompiled Jinja models
that mention it only in prose can also require clarification of their declarations.
Opaque macro-generated skills may not be detectable; authors must maintain the
explicit metadata and review `dbt compile` output separately. Metadata/spec
equivalence is not proven for uncompiled Jinja. Skills-free models may omit
metadata; `skills: []` explicitly declares no local skills. There is no fallback
to reading project source files, and no compile is triggered by skill planning.

## Plan, upload, deploy, smoke

Every manifest-dependent command reparses before reading the manifest.

```bash
dbt-cortex-agent skill plan --project-dir . --target sandbox \
  --agent orders_assistant --json
dbt-cortex-agent skill upload --project-dir . --target sandbox \
  --agent orders_assistant --json
```

Both commands avoid remote mutation as shown; fresh parsing writes local manifest
and log artifacts even without `--apply`. To upload independently, repeat
`skill upload` with an
explicit connection/database, both allowlists, and `--apply`. The CLI validates
the complete plan, deduplicates shared stage paths, and invokes Snow CLI only
after planning succeeds. All distinct stages are preflighted before any copy.
The resolved execution role (including `--role` overrides) is forwarded to both
Snow CLI DESCRIBE and copy operations and to skill runtime invocation.

A failure prevents subsequent copies and deployment. Applied standalone upload
and Agent deploy retain per-destination `phases` in JSON, including `stage_path`,
`phase`, and `completed`; partial failures exit `2` and emit their evidence on
stdout. A failed copy has `completed: false` but may have written some files.
Earlier successful destinations remain completed, later destinations are not
attempted, and nothing is rolled back. Capture command output for recovery;
the package does not persist a separate upload journal or verify per-file state.

Skill upload is a required preceding step for an Agent build. The materialization
independently checks that each declared stage-backed skill contains `SKILL.md`
and includes staged file state in the idempotency hash. dbt never uploads local
files.

Skill smoke is a subsequent live runtime check, not a deploy prerequisite:

```bash
dbt-cortex-agent skill smoke --project-dir . --target sandbox \
  --agent orders_assistant --database ANALYTICS_DEV --schema AGENTS
```

The preview maps logical Agent models to physical Agent names. A live call requires
the `runtime` extra, explicit `--connection`, both allowlists, and `--apply`.
`--agent-object` is allowed only for exactly one selected logical Agent.

Built-in native Agent Evaluation excludes skills. Verify skill selection with
smoke or another explicit integration test.