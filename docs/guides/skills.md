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

## Skill modes and rollback

Snowflake does not copy skills into an Agent version. A committed version stores
the skill path, and every invocation reads whatever is at that path at that
moment. Whether rolling back an Agent also rolls back its skill text therefore
depends only on whether the path's content can change. Each metadata declaration
chooses one of three modes:

| Mode | Declare | Deployed path | Rollback restores skill text |
|---|---|---|---|
| `immutable` (default) | stage source, no `mode` | `<path>/sha256-<digest>` | Yes |
| `overwrite` | stage source, `mode: overwrite` | `<path>` | No |
| Git | `type: git_integration`, tagged commit path | `@DB.SCHEMA.REPO/commits/<sha>/<folder>` | Yes |

```yaml
skills:
  - name: order_summary          # immutable by default
    source:
      type: stage
      path: "@{{ target.database }}.AGENTS.SKILL_STAGE/agents/orders_assistant/order_summary"
  - name: scratch_notes          # opt-in mutable folder
    mode: overwrite
    source:
      type: stage
      path: "@{{ target.database }}.AGENTS.SKILL_STAGE/library/scratch_notes"
  - name: policy_review          # pinned, tagged Git commit, never uploaded
    source:
      type: git_integration
      path: "@{{ target.database }}.AGENTS.SKILLS_REPO/commits/<40-character sha>/skills/policy_review"
```

`mode` belongs only in `config.meta.cortex_agent.skills`. The native model body
keeps the plain path and no mode; the comparison above ignores mode.

**Immutable.** The CLI hashes the published files: every file under the local
skill folder except hidden files and folders such as `.DS_Store`, keyed by sorted
relative path and content. Unchanged content keeps the same folder, so a
redeploy reuses it and commits no new Agent version. Changed content gets a new
folder; earlier folders are never overwritten, so earlier Agent versions keep
reading their own text. Shared skills share one folder across Agents. Upload
reads the folder back with `LIST` and compares each file's size and MD5 to the
local files before dbt runs. A folder that already holds a different or extra
file is refused, not repaired; a subset left by an interrupted upload is
completed without overwriting. The materialization resolves each immutable path
to `<path>/<digest>` only from `cortex_agent_skill_digests`, which `agent deploy`
passes after that verification. A direct `dbt build` without it fails rather than
falling back to the mutable folder. Content folders accumulate; remove an old one
only after no retained Agent version references it.

**Overwrite.** Files are copied over the declared folder in place, as earlier
releases did. The upload starts changing what every committed version that
references the folder reads, before dbt runs any check. Plans and deploy JSON
mark these uploads with `rollback_restores_skill_text: false` and a warning.
One stage path cannot be declared with two modes.

**Git.** Declare `type: git_integration` (`GIT_INTEGRATION` in the model body).
Snowflake rejects `GIT` in Agent specifications as invalid, so the package
refuses it up front. The path must name a full 40-character commit SHA; branch
and tag paths move after each `FETCH` and are rejected. The commit must also be
the commit of a tag: Snowflake resolves `commits/<sha>` only while that commit
is a fetched branch or tag head, so a pin to an untagged branch commit stops
resolving once the branch moves. Git skills are never uploaded. The repository
object, its API integration, `READ` for the deploying role, the tag, and a
`FETCH` that includes it are owned outside the package. Before committing a
version, the materialization lists `SKILL.md` at the commit path and checks
`SHOW GIT TAGS`, and stops with that guidance when either fails. Keep tags
immutable; moving or deleting one strands the versions that pin its commit.

The native model remains the deployment specification authority. Metadata is
the local upload and skill-smoke discovery contract, not a second renderer.
Readable, non-Jinja model YAML/JSON in the manifest is checked against metadata
by skill name, source type, and path. Missing, extra, duplicate, malformed, or
unresolved declarations fail before upload. Stage identifiers are normalized;
folder suffixes remain case-sensitive during comparison. Git paths are validated
as commit paths and included in skill smoke; other non-stage declarations are
validated but are not uploaded or included in stage-skill smoke.

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
and log artifacts even without `--apply`. Each planned upload reports `mode`,
`stage_path` (the declared base), `deployed_path`, and
`rollback_restores_skill_text`. To upload independently, repeat
`skill upload` with an
explicit connection/database, both allowlists, and `--apply`. The CLI validates
the complete plan, deduplicates shared stage paths, and invokes Snow CLI only
after planning succeeds. All distinct stages are preflighted before any copy.
The resolved execution role (including `--role` overrides) is forwarded to Snow
CLI DESCRIBE, LIST, and copy operations and to skill runtime invocation. Its
`dbt_vars` output is the `--vars` value a direct `dbt build` needs for immutable
skills.

A failure prevents subsequent copies and deployment. Applied standalone upload
and Agent deploy retain per-destination `phases` in JSON, including the deployed
path as `stage_path`, `phase`, `completed`, and a `detail` of `uploaded`,
`reused`, or `overwritten`; partial failures exit `2` and emit their evidence on
stdout. A failed copy has `completed: false` but may have written some files.
Earlier successful destinations remain completed, later destinations are not
attempted, and nothing is rolled back. Every completed destination was read back
and matched the local files at upload time.

Agent deploy uploads and verifies skills before dbt build. The materialization
independently checks that each declared stage or Git skill contains `SKILL.md`
and includes staged file state in the idempotency hash. That hash only decides
whether to commit a new version; for `overwrite` skills it does not let an older
version keep its text. dbt never uploads local files.

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