from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import Config

_LOGICAL_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class ScaffoldAction:
    path: Path
    action: str

    def to_dict(self, project_dir: Path) -> dict[str, str]:
        return {
            "path": self.path.relative_to(project_dir).as_posix(),
            "action": self.action,
        }


@dataclass(frozen=True)
class ScaffoldPlan:
    agent: str
    semantic_view_model: str | None
    with_eval: bool
    files: tuple[tuple[Path, str], ...]
    actions: tuple[ScaffoldAction, ...]

    def to_dict(self, project_dir: Path, *, applied: bool) -> dict[str, object]:
        return {
            "command": "agent scaffold",
            "applied": applied,
            "agent": self.agent,
            "semantic_view_model": self.semantic_view_model,
            "with_eval": self.with_eval,
            "actions": [action.to_dict(project_dir) for action in self.actions],
        }


def logical_agent_name(value: str) -> str:
    if not _LOGICAL_NAME.fullmatch(str(value)):
        raise ValueError(
            "--agent must start with a lowercase letter and contain only lowercase "
            "letters, numbers, and underscores"
        )
    return str(value)


def _display_name(agent: str) -> str:
    return " ".join(part.capitalize() for part in agent.split("_"))


def _model_sql(agent: str, semantic_view_model: str | None) -> str:
    dependency = ""
    tools = ""
    orchestration = (
        "Use only the capabilities declared in this Agent. Ask for clarification "
        "when the request cannot be answered safely."
    )
    if semantic_view_model:
        dependency = (
            f"{{% do ref('{semantic_view_model}') %}}\n"
            f"{{% set semantic_view_fqn = "
            f"dbt_cortex_agent.cortex_agent__semantic_view_fqn('{semantic_view_model}') %}}\n"
        )
        orchestration = (
            "Use GovernedAnalytics for questions supported by its governed semantics. "
            "Do not invent unavailable facts."
        )
        tools = """

tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: GovernedAnalytics
      description: Answers questions using the configured governed Semantic View.

tool_resources:
  GovernedAnalytics:
    semantic_view: "{{ semantic_view_fqn }}"
    execution_environment:
      type: warehouse
      warehouse: "{{ target.warehouse }}"
      query_timeout: 60
"""
    return f"""{dependency}{{{{
  config(
    materialized='cortex_agent',
    database=target.database,
    schema=var('cortex_agent_schema', 'AGENTS'),
    alias='{agent.upper()}',
    meta={{
      'agent_display_name': '{_display_name(agent)}',
      'agent_comment': 'Managed by dbt-cortex-agent',
      'deploy_alias': target.name,
      'cortex_agent': {{'enabled': true}}
    }}
  )
}}}}

models:
  orchestration: claude-sonnet-4-6

orchestration:
  budget:
    seconds: 60
    tokens: 16000

instructions:
  orchestration: |
    {orchestration}
  response: |
    Lead with the answer. Be concise, state material assumptions, and do not
    claim access to information that the configured capabilities did not return.
  sample_questions:
    - question: What questions can you help me answer?
{tools}"""


def _agent_yaml(agent: str) -> str:
    return f"""version: 2

models:
  - name: {agent}
    description: dbt-owned Cortex Agent. Replace this description with its governed purpose.
    config:
      access: protected
"""


def _skills_readme() -> str:
    return """# Agent skills

Create one folder per skill and place `SKILL.md` inside it. When ready, declare
matching stage sources in native top-level `skills` and in
`config.meta.cortex_agent.skills`. Fresh parse resolves the metadata used for
local upload and smoke planning; compiled YAML is not a discovery fallback.
"""


def _eval_sql(agent: str) -> str:
    return """{{ config(materialized='table', schema=var('cortex_eval_schema', 'EVAL')) }}

WITH capability_boundary AS (
    SELECT
        'What questions can you help me answer?' AS input_query,
        'The Agent should describe only its configured capabilities.' AS ground_truth_output,
        ARRAY_CONSTRUCT() AS ground_truth_invocations,
        OBJECT_CONSTRUCT(
            'category', 'capability_boundary',
            'test_type', 'in_scope',
            'ground_truth_ref', 'capability_boundary'
        ) AS custom_criteria
)

{{ dbt_cortex_agent.cortex_eval__assemble(['capability_boundary']) }}
"""


def _eval_yaml(agent: str) -> str:
    return f"""version: 2

models:
  - name: {agent}_core
    description: Starter evaluation dataset; replace or extend before baseline acceptance.
    config:
      materialized: table
      schema: "{{{{ var('cortex_eval_schema', 'EVAL') }}}}"
      meta:
        cortex_eval:
          name: core
          agent: {agent}
          description: Initial capability-boundary check.
          metrics:
            - answer_correctness
            - logical_consistency
          thresholds:
            answer_correctness: 0.60
            logical_consistency: 0.60
          questions:
            - id: capability_boundary
              test_type: in_scope
              expected_tools: []
              ground_truth_ref: capability_boundary
    columns:
      - name: input_query
        data_tests:
          - not_null
          - unique
      - name: output
        data_tests:
          - not_null
"""


def scaffold_contents(
    agent: str,
    semantic_view_model: str | None = None,
    *,
    with_eval: bool = False,
) -> dict[str, str]:
    name = logical_agent_name(agent)
    semantic_model = logical_agent_name(semantic_view_model) if semantic_view_model else None
    root = f"models/agents/{name}"
    contents = {
        f"{root}/{name}.sql": _model_sql(name, semantic_model),
        f"{root}/agent.yml": _agent_yaml(name),
        f"{root}/skills/README.md": _skills_readme(),
    }
    if with_eval:
        contents[f"{root}/evals/{name}_core.sql"] = _eval_sql(name)
        contents[f"{root}/evals/core.yml"] = _eval_yaml(name)
    return {path: content.rstrip("\n") + "\n" for path, content in contents.items()}


def build_scaffold_plan(
    config: Config,
    agent: str,
    semantic_view_model: str | None = None,
    *,
    with_eval: bool = False,
) -> ScaffoldPlan:
    if not config.project_dir.is_dir():
        raise FileNotFoundError(f"dbt project directory not found: {config.project_dir}")
    project_file = config.project_dir / "dbt_project.yml"
    if not project_file.is_file():
        raise FileNotFoundError(f"dbt_project.yml not found: {project_file}")

    contents = scaffold_contents(agent, semantic_view_model, with_eval=with_eval)
    files: list[tuple[Path, str]] = []
    actions: list[ScaffoldAction] = []
    for relative_path, content in contents.items():
        destination = config.project_dir / relative_path
        if destination.exists():
            if not destination.is_file() or destination.read_text(encoding="utf-8") != content:
                raise FileExistsError(
                    f"Agent scaffold collision at {destination}; existing content differs"
                )
            actions.append(ScaffoldAction(destination, "unchanged"))
        else:
            files.append((destination, content))
            actions.append(ScaffoldAction(destination, "create"))

    for destination, _ in files:
        parent = destination.parent
        while parent != config.project_dir:
            if parent.exists() and not parent.is_dir():
                raise FileExistsError(f"Agent scaffold collision at {parent}; expected a directory")
            parent = parent.parent
    return ScaffoldPlan(
        logical_agent_name(agent),
        logical_agent_name(semantic_view_model) if semantic_view_model else None,
        with_eval,
        tuple(files),
        tuple(actions),
    )


def apply_scaffold_plan(plan: ScaffoldPlan) -> tuple[Path, ...]:
    changed: list[Path] = []
    for path, content in plan.files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        changed.append(path)
    return tuple(changed)
