from __future__ import annotations

import builtins

import pytest

from dbt_cortex_agent.invoke import invoke_agent, parse_sse, smoke_skills


def test_missing_invoke_dependency_message_names_runtime_extra(monkeypatch):
    real_import = builtins.__import__

    def fail_snowflake(name, *args, **kwargs):
        if name == "snowflake.connector":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_snowflake)
    with pytest.raises(RuntimeError, match=r"dbt-cortex-agent\[runtime\]"):
        invoke_agent("DB", "SCHEMA", "AGENT", "question", "connection")
from dbt_cortex_agent.manifest import SkillDeclaration


def test_parse_sse_captures_tool_use_and_answer():
    lines = [
        "event: response.tool_use",
        'data: {"name":"server_skill","input":{"skill_name":"triage"}}',
        "event: response.text.delta",
        'data: {"text":"done"}',
        "data: [DONE]",
    ]

    result = parse_sse(lines)

    assert result["tool_uses"][0]["input"]["skill_name"] == "triage"
    assert result["answer"] == "done"


def test_smoke_skills_uses_direct_invoker_and_requires_server_skill(tmp_path):
    skill = SkillDeclaration("agent", "triage", "stage", "@DB.S.STAGE/triage", tmp_path)
    calls = []

    def success(*args):
        calls.append(args)
        return {"tool_uses": [{"name": "server_skill", "input": {"skill_name": "triage"}}]}

    assert smoke_skills(
        [skill],
        database="DB",
        schema="S",
        agent_names={"agent": "AGENT"},
        connection="conn",
        endpoint="https://example.snowflakecomputing.com",
        invoker=success,
    ) == ["triage"]
    assert calls[0][:5] == (
        "DB",
        "S",
        "AGENT",
        "Use the triage skill and summarize the expected next actions.",
        "conn",
    )

    with pytest.raises(RuntimeError, match="server_skill"):
        smoke_skills(
            [skill],
            database="DB",
            schema="S",
            agent_names={"agent": "AGENT"},
            connection="conn",
            invoker=lambda *args: {"tool_uses": []},
        )


def test_smoke_skills_maps_each_logical_agent_to_its_physical_object(tmp_path):
    skills = [
        SkillDeclaration("a", "one", "stage", "@DB.S.STAGE/one", tmp_path),
        SkillDeclaration("b", "two", "stage", "@DB.S.STAGE/two", tmp_path),
    ]
    calls = []

    def invoke(*args):
        calls.append(args)
        skill_name = args[3].split()[2]
        return {"tool_uses": [{"name": "server_skill", "input": {"skill_name": skill_name}}]}

    assert smoke_skills(
        skills,
        database="DB",
        schema="S",
        agent_names={"a": "AGENT_A", "b": "AGENT_B"},
        connection="conn",
        invoker=invoke,
    ) == ["one", "two"]
    assert [call[2] for call in calls] == ["AGENT_A", "AGENT_B"]


@pytest.mark.parametrize(
    "lines",
    [
        ["event: response.text.delta", "data: not-json", "data: [DONE]"],
        ["event: response.text.delta", 'data: {"text":"partial"}'],
    ],
)
def test_parse_sse_rejects_malformed_or_unterminated_stream(lines):
    with pytest.raises(RuntimeError):
        parse_sse(lines)


def test_runtime_source_has_no_repository_or_uv_assumptions():
    import dbt_cortex_agent

    source_dir = dbt_cortex_agent.__path__[0]
    forbidden = ("sys.path", "agent-evaluation", "scripts/deploy_", "uv run", "shell=True")
    for path in __import__("pathlib").Path(source_dir).glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not any(value in text for value in forbidden), path


def test_direct_invocation_rejects_non_snowflake_endpoint(monkeypatch):
    import sys
    import types

    class Cursor:
        def close(self):
            pass

    class Connection:
        rest = types.SimpleNamespace(token="secret")

        def cursor(self):
            return Cursor()

        def close(self):
            pass

    connector = types.SimpleNamespace(connect=lambda **kwargs: Connection())
    snowflake = types.ModuleType("snowflake")
    snowflake.connector = connector
    monkeypatch.setitem(sys.modules, "snowflake", snowflake)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector)

    with pytest.raises(ValueError, match="snowflakecomputing.com"):
        invoke_agent("DB", "S", "A", "question", "conn", "https://example.com")


def test_direct_invocation_passes_bounded_http_timeout(monkeypatch):
    import sys
    import types

    class Cursor:
        def close(self):
            pass

    class Connection:
        rest = types.SimpleNamespace(token="secret")

        def cursor(self):
            return Cursor()

        def close(self):
            pass

    class Response:
        def __enter__(self):
            return iter(['data: [DONE]'])

        def __exit__(self, *args):
            pass

    connector = types.SimpleNamespace(connect=lambda **kwargs: Connection())
    snowflake = types.ModuleType("snowflake")
    snowflake.connector = connector
    monkeypatch.setitem(sys.modules, "snowflake", snowflake)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector)
    observed = []
    monkeypatch.setattr(
        "dbt_cortex_agent.invoke.urlopen",
        lambda request, timeout: observed.append(timeout) or Response(),
    )

    assert invoke_agent(
        "DB", "S", "A", "question", "conn",
        "https://example.snowflakecomputing.com", timeout=12,
    )["answer"] == ""
    assert observed == [12]
