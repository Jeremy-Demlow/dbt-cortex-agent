# Lifecycle and versioning

`cortex_agent__deploy` renders a deterministic specification and defaults to
`dry_run=true`.

On a mutating canonical deployment the package:

1. validates the exposure and projection,
2. checks the allowed target,
3. verifies staged `SKILL.md` files,
4. computes spec and staged-skill hashes,
5. skips an unchanged deployment,
6. creates or modifies the LIVE draft,
7. commits a Snowflake Agent version,
8. applies the configured deploy alias,
9. optionally attaches MCP servers.

Aliases are moved without changing the specification:

- `cortex_agent__set_alias`
- `cortex_agent__promote_alias`
- `cortex_agent__rollback_alias`

MCP attachment is outside the spec/skill hash. If an unchanged deployment skipped
before an intended MCP reattachment, use the documented force option only after
reviewing the resulting version mutation.
