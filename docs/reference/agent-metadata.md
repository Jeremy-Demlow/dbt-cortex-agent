# Agent metadata reference

Agent metadata lives at `exposures[].config.meta.cortex_agent`.

## Required core fields

| Field | Type | Contract |
|---|---|---|
| `enabled` | boolean | Must be true for discovery |
| `snowflake_name` | string | Base Agent name |
| `tools` | list | At least one implemented tool |

## Naming, access, model, and instructions

| Field | Type | Behavior |
|---|---|---|
| `naming.<target>` | string | Explicit target-specific Agent name |
| `access.usage_roles` | list | Used by Agent-object grant macro |
| `access.monitor_roles` | list | Roles that inspect or evaluate Agent observability |
| `model.orchestration` | string | Orchestration model; package default applies when absent |
| `orchestration.budget.seconds/tokens` | number | Rendered budget |
| `instructions.orchestration` | string | Orchestration instructions |
| `instructions.response` | string | Response instructions |
| `sample_questions` | list of strings | Rendered as question objects |

`description`, `profile`, and `versioning.strategy` are currently documentary
metadata; they are not rendered into the Agent specification.

## Complete public field inventory

| Field path | Type | Required | Default / behavior |
|---|---|---:|---|
| `enabled` | boolean | Yes | Must be `true` for discovery |
| `snowflake_name` | string | Yes | Base name when no target mapping exists |
| `naming.<target>` | string | No | Falls back to environment suffix rules |
| `description` | string | No | Documentary only |
| `access.usage_roles[]` | string | No | Used only by `cortex_agent__grant_usage` |
| `access.monitor_roles[]` | string | No | Grants `MONITOR ON AGENT` through `cortex_agent__grant_usage` |
| `versioning.strategy` | string | No | Documentary only |
| `versioning.<target>.deploy_alias` | string | No | Alias applied after commit |
| `versioning.<target>.promotion_alias` | string | No | Documentary promotion intent |
| `profile.display_name` | string | No | Documentary only |
| `profile.color` | string | No | Documentary only |
| `model.orchestration` | string | No | `cortex_agent_default_model` |
| `orchestration.budget.seconds` | number | No | Rendered when supplied |
| `orchestration.budget.tokens` | number | No | Rendered when supplied |
| `instructions.orchestration` | string | No | Empty string |
| `instructions.response` | string | No | Empty string |
| `sample_questions[]` | string | No | Empty list |
| `tools[]` | object | Yes | At least one tool |
| `tools[].name` | string | Yes | Rendered tool name |
| `tools[].type` | string | Yes | Supported types listed below |
| `tools[].description` | string | No | Empty string |
| `tools[].warehouse` | string | No | `target.warehouse` |
| `tools[].query_timeout` | number | No | `300` |
| `tools[].semantic_view_model` | string | Analyst only | Manifest-resolved semantic view |
| `tools[].search_service` | string | Search only | Pre-existing service FQN |
| `tools[].access.usage_roles[]` | string | Search only | Roles granted `USAGE` on the exact Search service by the Agent grant lifecycle |
| `tools[].identifier` | string | Generic only | Pre-existing procedure FQN |
| `capabilities.web_search.enabled` | boolean | No | Disabled when absent |
| `capabilities.web_search.max_results` | number | No | Resource omitted when absent |
| `capabilities.web_search.usage_policy` | string | No | Documentary only |
| `capabilities.data_to_chart.enabled` | boolean | No | Disabled when absent |
| `capabilities.data_to_chart.description` | string | No | Default chart description |
| `capabilities.code_execution.enabled` | boolean | No | Also gated by `code_execution_enabled` |
| `capabilities.code_execution.usage_policy` | string | No | Documentary only |
| `capabilities.code_execution.artifact_repositories` | any | No | Rendered into code-execution resources when supplied |
| `capabilities.code_execution.external_access_integrations` | any | No | Rendered into code-execution resources when supplied |
| `capabilities.skills[]` | object | No | Rendered in the full Agent specification |
| `capabilities.skills[].name` | string | Yes per skill | Rendered name |
| `capabilities.skills[].description` | string | No | Documentary; `SKILL.md` is authoritative |
| `capabilities.skills[].source.type` | string | Yes per skill | Stage readiness supports `stage` |
| `capabilities.skills[].source.path` | string | Yes per skill | Rendered unchanged |
| `capabilities.mcp_connectors[]` | object | No | Attached through separate Agent DDL |
| `capabilities.mcp_connectors[].name` | string | No | Documentary only |
| `capabilities.mcp_connectors[].enabled` | boolean | No | Disabled when absent |
| `capabilities.mcp_connectors[].server` | string | Yes when enabled | External MCP server FQN |
| `capabilities.mcp_connectors[].usage_policy` | string | No | Documentary only |

## Tools

Common fields are listed in the complete inventory above.

| Type | Required field | Resource rendering |
|---|---|---|
| `cortex_analyst_text_to_sql` | `semantic_view_model` | Manifest-resolved semantic-view FQN plus warehouse |
| `cortex_search` | `search_service` | Pre-existing three-part service FQN; optional `access.usage_roles` declares least-privilege query access |
| `generic` | `identifier` | Pre-existing procedure identifier |

Unknown tool types fail validation. Analyst model names must resolve uniquely to a
dbt model materialized as `semantic_view`.

Usage-policy and descriptive capability fields may be retained as governance
metadata without being rendered. `evaluation_supported` is not a public metadata
field and never filters the rendered/deployed Agent specification. Built-in evaluation
coverage is validated separately from deployment: Analyst, Cortex Search, `web_search`,
and declared generic custom tool names may be expected; skills, MCP, code execution,
and other capability tools require separate proof.
