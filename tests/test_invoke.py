from __future__ import annotations

import builtins
from pathlib import Path

import pytest

# Evidence: TC-025-08 TC-027-01 TC-027-02 TC-027-03 TC-027-04 TC-027-05
# Evidence: TC-027-06 TC-027-07 TC-027-08 TC-027-09 TC-027-10
from dbt_cortex_agent.invoke import (
    AgentEvent,
    compact_agent_output,
    invoke_agent,
    parse_sse,
    smoke_skills,
    write_raw_events,
)
from dbt_cortex_agent.manifest import SkillDeclaration

ROOT = Path(__file__).parents[1]


def test_missing_invoke_dependency_message_names_runtime_extra(monkeypatch):
    real_import = builtins.__import__

    def fail_snowflake(name, *args, **kwargs):
        if name == "snowflake.connector":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_snowflake)
    with pytest.raises(RuntimeError, match=r"dbt-cortex-agent\[runtime\]"):
        invoke_agent("DB", "SCHEMA", "AGENT", "question", "connection")


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


def test_recorded_protocol_fixture_replays_additive_current_response() -> None:
    fixture = ROOT / "tests/fixtures/protocol/current_response.sse"
    result = parse_sse(fixture.read_text(encoding="utf-8").splitlines(keepends=True))

    assert result["answer"] == "$405.75"
    assert result["tool_uses"][0]["name"] == "OrdersAnalytics"
    assert result["sql_queries"] == ["select sum(revenue) from orders"]
    assert result["result_summaries"][0]["preview"] == [[405.75]]
    assert result["charts"] == [{"type": "bar"}]
    assert result["annotations"][0]["kind"] == "citation"
    assert result["metadata"]["resolved_version"] == "VERSION$2"


def test_raw_event_artifact_is_explicit_bounded_and_collision_safe(tmp_path, monkeypatch) -> None:
    events = [AgentEvent("response", {"status": "completed"})]
    target = tmp_path / "raw" / "events.jsonl"

    assert write_raw_events(events, target) == target
    assert '"event": "response"' in target.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        write_raw_events(events, target)

    monkeypatch.setattr("dbt_cortex_agent.invoke.MAX_RAW_EVENT_BYTES", 1)
    with pytest.raises(ValueError, match="byte limit"):
        write_raw_events(events, tmp_path / "too-large.jsonl")


def test_documented_terminal_response_completes_without_done_marker():
    lines = [
        "event: response.text.delta\n",
        'data: {"text":"partial"}\n',
        "\n",
        "event: response\n",
        'data: {"role":"assistant","content":[{"type":"text","text":"final answer"}],'
        '"warnings":[{"code":"W1","message":"degraded"}],'
        '"metadata":{"run_id":"run-1"},"status":"completed"}\n',
        "\n",
    ]

    result = parse_sse(lines)

    assert result["answer"] == "final answer"
    assert result["metadata"]["run_id"] == "run-1"
    assert result["metadata"]["warnings"][0]["code"] == "W1"


def test_parse_sse_frames_multiline_events_and_bounds_results():
    import json

    rows = [[index, f"value-{index}"] for index in range(8)]
    payload = json.dumps(
        {
            "content": [
                {
                    "json": {
                        "sql": "select 1",
                        "result_set": {
                            "resultSetMetaData": {"rowType": [{"name": "ID"}, {"name": "VALUE"}]},
                            "data": rows,
                        },
                    }
                }
            ]
        }
    )
    midpoint = payload.index('"result_set"')
    lines = [
        "event: response.tool_result\n",
        f"data: {payload[:midpoint]}\n",
        f"data: {payload[midpoint:]}\n",
        "\n",
        "data: [DONE]\n",
        "\n",
    ]

    result = parse_sse(lines)

    assert result["sql_queries"] == ["select 1"]
    assert result["result_summaries"] == [
        {
            "row_count": 8,
            "column_count": 2,
            "columns": ["ID", "VALUE"],
            "preview": rows[:5],
            "truncated": True,
        }
    ]


def test_compact_output_omits_result_payloads():
    result = {
        "answer": "Revenue was 10.",
        "tool_uses": [{"name": "analyst", "input": {"large": "secret" * 1000}}],
        "sql_queries": ["select 10"],
        "result_summaries": [{"row_count": 1, "preview": [["large" * 1000]]}],
        "metadata": {"resolved_version": "VERSION$2"},
        "duration_seconds": 1.25,
    }

    output = compact_agent_output(result)

    assert output == (
        "Revenue was 10.\nTools: analyst\nSQL statements: 1\n"
        "Result sets: 1 (1 rows)\nVersion: VERSION$2\nDuration: 1.25s"
    )
    assert "secret" not in output and "largelarge" not in output


def test_smoke_skills_uses_direct_invoker_and_requires_server_skill(tmp_path):
    skill = SkillDeclaration("agent", "triage", "stage", "@DB.S.STAGE/triage", tmp_path)
    calls = []

    def success(*args):
        calls.append(args)
        return {"tool_uses": [{"name": "server_skill", "input": {"skill_name": "triage"}}]}

    assert smoke_skills(
        [skill],
        agent_names={"agent": {"database": "DB", "schema": "S", "object_name": "AGENT"}},
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
            agent_names={"agent": {"database": "DB", "schema": "S", "object_name": "AGENT"}},
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
        agent_names={
            "a": {"database": "DB_A", "schema": "S", "object_name": "AGENT_A"},
            "b": {"database": "DB_B", "schema": "OTHER", "object_name": "AGENT_B"},
        },
        connection="conn",
        invoker=invoke,
    ) == ["one", "two"]
    assert [call[2] for call in calls] == ["AGENT_A", "AGENT_B"]
    assert [(call[0], call[1]) for call in calls] == [("DB_A", "S"), ("DB_B", "OTHER")]


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
            return iter(["data: [DONE]"])

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

    assert (
        invoke_agent(
            "DB",
            "S",
            "A",
            "question",
            "conn",
            "https://example.snowflakecomputing.com",
            timeout=12,
        )["answer"]
        == ""
    )
    assert observed == [12]


def test_direct_invocation_uses_versioned_rest_path(monkeypatch):
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
            return iter(["data: [DONE]"])

        def __exit__(self, *args):
            pass

    connector = types.SimpleNamespace(connect=lambda **kwargs: Connection())
    snowflake = types.ModuleType("snowflake")
    snowflake.connector = connector
    monkeypatch.setitem(sys.modules, "snowflake", snowflake)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector)
    requests = []
    monkeypatch.setattr(
        "dbt_cortex_agent.invoke.urlopen",
        lambda request, timeout: requests.append(request.full_url) or Response(),
    )

    invoke_agent(
        "DB",
        "S",
        "A!VERSION$2",
        "question",
        "conn",
        "https://example.snowflakecomputing.com",
    )

    assert requests == [
        "https://example.snowflakecomputing.com/api/v2/databases/DB/schemas/S/agents/A/versions/VERSION%242:run"
    ]


def test_direct_invocation_sends_explicit_runtime_role(monkeypatch):
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
            return iter(["data: [DONE]"])

        def __exit__(self, *args):
            pass

    connector = types.SimpleNamespace(connect=lambda **kwargs: Connection())
    snowflake = types.ModuleType("snowflake")
    snowflake.connector = connector
    monkeypatch.setitem(sys.modules, "snowflake", snowflake)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector)
    requests = []
    monkeypatch.setattr(
        "dbt_cortex_agent.invoke.urlopen",
        lambda request, timeout: requests.append(request) or Response(),
    )

    invoke_agent(
        "DB",
        "S",
        "A",
        "question",
        "conn",
        "https://example.snowflakecomputing.com",
        role="runtime_role",
    )

    assert requests[0].headers["X-snowflake-role"] == "RUNTIME_ROLE"
