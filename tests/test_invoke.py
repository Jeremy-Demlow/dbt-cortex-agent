from __future__ import annotations

import builtins
import io
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from urllib.error import HTTPError

import pytest

# Evidence: TC-025-08 TC-027-01 TC-027-02 TC-027-03 TC-027-04 TC-027-05
# Evidence: TC-027-06 TC-027-07 TC-027-08 TC-027-09 TC-027-10
from dbt_cortex_agent.invoke import (
    AgentEvent,
    AgentInvocationError,
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
        def __iter__(self):
            return iter(["data: [DONE]"])

        def close(self):
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
    assert len(observed) == 1
    assert 0 < observed[0] <= 12


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
        def __iter__(self):
            return iter(["data: [DONE]"])

        def close(self):
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
        def __iter__(self):
            return iter(["data: [DONE]"])

        def close(self):
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


@pytest.fixture
def runtime_transport(monkeypatch):  # noqa: C901
    state = SimpleNamespace(
        clock=100.0,
        connect_delay=0,
        read_delay=0,
        closed=[],
        connect_args=None,
        cursor_error=None,
        connect_error=None,
        read_error=None,
        close_errors={},
        requests=[],
        query_timeouts=[],
        read_sizes=[],
    )

    def close(name):
        state.closed.append(name)
        if name in state.close_errors:
            raise state.close_errors[name]

    class Cursor:
        def execute(self, sql, *, timeout):
            state.query_timeouts.append(timeout)

        def fetchone(self):
            return ("org", "account")

        def close(self):
            close("cursor")

    class Connection:
        rest = SimpleNamespace(token="test-token")

        def cursor(self):
            if state.cursor_error:
                raise state.cursor_error
            return Cursor()

        def close(self):
            close("connection")

    class Response(io.BytesIO):
        def readline(self, size=-1):
            state.read_sizes.append(size)
            state.clock += state.read_delay
            if state.read_error and self.tell() == len(self.getvalue()):
                raise state.read_error
            return super().readline(size)

        def close(self):
            if self.closed:
                return
            super().close()
            if self is state.response:
                close("response")

    def connect(**kwargs):
        state.connect_args = kwargs
        state.clock += state.connect_delay
        if state.connect_error:
            raise state.connect_error
        return Connection()

    def open_response(request, timeout):
        state.requests.append((request, timeout))
        return state.response

    state.response = Response(b"data: [DONE]\n")
    state.set_stream = lambda stream: setattr(state, "response", Response(stream))
    connector = SimpleNamespace(connect=connect)
    snowflake = ModuleType("snowflake")
    snowflake.connector = connector
    monkeypatch.setitem(sys.modules, "snowflake", snowflake)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector)
    monkeypatch.setattr("dbt_cortex_agent.invoke.urlopen", open_response)
    monkeypatch.setattr("dbt_cortex_agent.invoke.time.monotonic", lambda: state.clock)
    yield state
    state.close_errors.clear()
    state.response.close()


PARTIAL_STREAM = b'event: response.text.delta\ndata: {"text":"partial"}\n\n'


@pytest.mark.parametrize(
    "ending, message",
    [
        (b'event: error\ndata: {"message":"service failed"}\n\ndata: [DONE]\n', "service failed"),
        (b"event: response\ndata: not-json\n\n", "Malformed Agent SSE JSON"),
        (b"event: response\ndata: []\n\n", "must be a JSON object"),
        (b"\xff\n", "utf-8"),
        (b"", "ended before"),
    ],
)
def test_runtime_partial_evidence_survives_stream_failure(
    runtime_transport, tmp_path, ending, message
):
    runtime_transport.set_stream(PARTIAL_STREAM + ending)
    target = tmp_path / "events.jsonl"
    with pytest.raises(AgentInvocationError, match=message) as failure:
        invoke_agent("DB", "S", "A", "question", "conn", raw_event_path=target)
    assert failure.value.result["answer"] == "partial"
    assert failure.value.result["errors"]
    assert failure.value.raw_event_path == target
    raw = [json.loads(line) for line in target.read_text().splitlines()]
    assert raw[0] == {"event": "response.text.delta", "data": {"text": "partial"}}
    assert runtime_transport.closed[-3:] == ["response", "cursor", "connection"]


@pytest.mark.parametrize(
    "limit, value, ending",
    [
        ("MAX_STREAM_BYTES", len(PARTIAL_STREAM) + 5, b":" + b"x" * 1000),
        ("MAX_RAW_EVENT_BYTES", 80, PARTIAL_STREAM),
        ("MAX_AGENT_EVENTS", 1, PARTIAL_STREAM),
    ],
)
def test_runtime_limits_are_incremental_with_partial_evidence(
    runtime_transport,
    tmp_path,
    monkeypatch,
    limit,
    value,
    ending,
):
    monkeypatch.setattr(f"dbt_cortex_agent.invoke.{limit}", value)
    runtime_transport.set_stream(PARTIAL_STREAM + ending + b"\ndata: [DONE]\n")
    target = tmp_path / "events.jsonl"
    with pytest.raises(AgentInvocationError, match="limit") as failure:
        invoke_agent("DB", "S", "A", "question", "conn", raw_event_path=target)
    assert failure.value.result["answer"] == "partial"
    assert len(target.read_text().splitlines()) == 1
    assert target.stat().st_size <= (value if limit == "MAX_RAW_EVENT_BYTES" else 1_000_000)
    assert all(0 < size <= 1_000_001 for size in runtime_transport.read_sizes)


def test_runtime_deadline_includes_setup_and_slow_stream(runtime_transport, tmp_path):
    runtime_transport.set_stream(PARTIAL_STREAM + b": heartbeat\n" * 20)
    runtime_transport.connect_delay = 2
    runtime_transport.read_delay = 1
    with pytest.raises(AgentInvocationError, match="deadline") as failure:
        invoke_agent(
            "DB", "S", "A", "question", "conn", timeout=10, raw_event_path=tmp_path / "events.jsonl"
        )
    assert runtime_transport.connect_args == {
        "connection_name": "conn",
        "login_timeout": 10,
        "network_timeout": 10,
        "socket_timeout": 10,
    }
    assert runtime_transport.query_timeouts == [8]
    assert runtime_transport.requests[0][1] == 8
    assert failure.value.result["answer"] == "partial"
    assert failure.value.result["duration_seconds"] == 10
    assert len(runtime_transport.read_sizes) == 8


def test_setup_overrun_closes_connection_without_opening_http(runtime_transport):
    runtime_transport.connect_delay = 11
    with pytest.raises(AgentInvocationError, match="deadline"):
        invoke_agent("DB", "S", "A", "question", "conn", timeout=10)
    assert runtime_transport.requests == []
    assert runtime_transport.closed[-1:] == ["connection"]


@pytest.mark.parametrize("error_type", [AssertionError, TypeError, AttributeError])
def test_runtime_programming_defect_propagates_despite_cleanup(runtime_transport, error_type):
    primary = error_type("programming defect")
    runtime_transport.set_stream(PARTIAL_STREAM)
    runtime_transport.read_error = primary
    runtime_transport.close_errors = {
        name: OSError(name) for name in ("response", "cursor", "connection")
    }
    with pytest.raises(error_type) as failure:
        invoke_agent("DB", "S", "A", "question", "conn")
    assert failure.value is primary
    assert [str(error) for error in primary.cleanup_errors] == ["response", "cursor", "connection"]
    assert runtime_transport.closed[-3:] == ["response", "cursor", "connection"]


@pytest.mark.parametrize("phase", ["connect", "cursor", "read", "close"])
def test_runtime_acquisition_and_independent_cleanup(runtime_transport, phase, tmp_path):
    connector_error = type(
        "OperationalError", (Exception,), {"__module__": "snowflake.connector.errors"}
    )
    primary = connector_error("primary")
    if phase == "connect":
        runtime_transport.connect_error = primary
    elif phase == "cursor":
        runtime_transport.cursor_error = primary
    elif phase == "read":
        runtime_transport.set_stream(PARTIAL_STREAM)
        runtime_transport.read_error = primary
    runtime_transport.close_errors = {
        name: OSError(f"close {name}") for name in ("response", "cursor", "connection")
    }
    with pytest.raises(AgentInvocationError) as failure:
        invoke_agent("DB", "S", "A", "question", "conn", raw_event_path=tmp_path / "events.jsonl")
    if phase != "close":
        assert failure.value.__cause__ is primary
        assert str(failure.value) == "primary"
    else:
        assert str(failure.value) == "close response"
    expected = {
        "connect": [],
        "cursor": ["connection"],
        "read": ["response", "cursor", "connection"],
        "close": ["response", "cursor", "connection"],
    }[phase]
    assert runtime_transport.closed == expected
    if phase == "read":
        assert failure.value.result["answer"] == "partial"
        assert failure.value.result["metadata"]["cleanup_errors"] == [
            "close response",
            "close cursor",
            "close connection",
        ]


def test_raw_write_failure_cannot_mask_stream_failure(runtime_transport, monkeypatch, tmp_path):
    runtime_transport.set_stream(PARTIAL_STREAM)
    monkeypatch.setattr(
        "dbt_cortex_agent.invoke.write_raw_events",
        lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(AgentInvocationError, match="ended before") as failure:
        invoke_agent("DB", "S", "A", "question", "conn", raw_event_path=tmp_path / "events.jsonl")
    assert failure.value.result["answer"] == "partial"
    assert "disk full" in failure.value.result["errors"]
    assert failure.value.raw_event_path is None


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_runtime_budget_fails_before_acquisition(runtime_transport, timeout):
    with pytest.raises(ValueError):
        invoke_agent("DB", "S", "A", "question", "conn", timeout=timeout)
    assert runtime_transport.connect_args is None


def test_runtime_without_raw_opt_in_still_retains_normalized_failure(
    runtime_transport, monkeypatch
):
    runtime_transport.set_stream(PARTIAL_STREAM)
    monkeypatch.setattr(
        "dbt_cortex_agent.invoke.write_raw_events",
        lambda *_args: pytest.fail("raw artifact written without opt-in"),
    )
    with pytest.raises(AgentInvocationError) as failure:
        invoke_agent("DB", "S", "A", "question", "conn")
    assert failure.value.result["answer"] == "partial"
    assert failure.value.raw_event_path is None


def test_runtime_direct_collision_fails_before_connection(runtime_transport, tmp_path):
    target = tmp_path / "events.jsonl"
    target.write_text("existing evidence")
    with pytest.raises(FileExistsError):
        invoke_agent("DB", "S", "A", "question", "conn", raw_event_path=target)
    assert runtime_transport.connect_args is None
    assert target.read_text() == "existing evidence"


def test_unframed_stream_is_bounded_before_json_decode(runtime_transport, tmp_path, monkeypatch):
    monkeypatch.setattr("dbt_cortex_agent.invoke.MAX_STREAM_BYTES", 32)
    runtime_transport.set_stream(b'data: {"text":"' + b"x" * 5000)
    target = tmp_path / "events.jsonl"
    with pytest.raises(AgentInvocationError, match="byte limit") as failure:
        invoke_agent("DB", "S", "A", "question", "conn", raw_event_path=target)
    assert runtime_transport.read_sizes == [33]
    assert failure.value.result["answer"] == ""
    assert target.read_bytes() == b""


def test_runtime_eof_read_checks_deadline_after_blocking(runtime_transport):
    runtime_transport.set_stream(PARTIAL_STREAM)
    runtime_transport.read_delay = 1
    with pytest.raises(AgentInvocationError, match="deadline") as failure:
        invoke_agent("DB", "S", "A", "question", "conn", timeout=4)
    assert failure.value.result["answer"] == "partial"
    assert len(runtime_transport.read_sizes) == 4


def test_truncated_http_read_preserves_accepted_events(runtime_transport):
    from http.client import IncompleteRead

    runtime_transport.set_stream(PARTIAL_STREAM)
    runtime_transport.read_error = IncompleteRead(b"unframed bytes")
    with pytest.raises(AgentInvocationError, match="IncompleteRead") as failure:
        invoke_agent("DB", "S", "A", "question", "conn")
    assert failure.value.result["answer"] == "partial"
    assert failure.value.__cause__ is runtime_transport.read_error
    assert runtime_transport.closed[-3:] == ["response", "cursor", "connection"]


@pytest.mark.parametrize(
    "failing_closes",
    [(), ("response",), ("cursor",), ("connection",), ("response", "cursor", "connection")],
)
@pytest.mark.parametrize("raw_evidence", [False, True])
def test_http_error_closes_owned_body_and_retains_primary(
    runtime_transport, monkeypatch, tmp_path, failing_closes, raw_evidence
):
    runtime_transport.set_stream(PARTIAL_STREAM)
    runtime_transport.close_errors = {name: OSError(f"close {name}") for name in failing_closes}
    primary = HTTPError(
        "https://example.snowflakecomputing.com",
        503,
        "service unavailable",
        {},
        runtime_transport.response,
    )
    original_close = primary.close
    close_calls = []

    def close_error():
        close_calls.append(True)
        original_close()

    def reject_request(request, timeout):
        raise primary

    monkeypatch.setattr(primary, "close", close_error)
    monkeypatch.setattr("dbt_cortex_agent.invoke.urlopen", reject_request)
    target = tmp_path / "events.jsonl" if raw_evidence else None
    with pytest.raises(AgentInvocationError, match="HTTP Error 503") as failure:
        invoke_agent("DB", "S", "A!VERSION$2", "question", "conn", raw_event_path=target)

    assert failure.value.__cause__ is primary
    assert str(failure.value) == str(primary)
    assert close_calls == [True]
    assert runtime_transport.response.closed
    assert runtime_transport.closed == ["response", "cursor", "connection"]
    assert runtime_transport.read_sizes == []
    result = failure.value.result
    assert result["answer"] == ""
    assert result["errors"] == [str(primary)]
    assert result["metadata"]["agent_fqn"] == "DB.S.A"
    assert result["metadata"]["requested_version"] == "VERSION$2"
    assert result["metadata"].get("cleanup_errors", []) == [
        f"close {name}" for name in failing_closes
    ]
    assert getattr(primary, "cleanup_errors", []) == [
        runtime_transport.close_errors[name] for name in failing_closes
    ]
    assert failure.value.raw_event_path == target
    if target is not None:
        assert target.read_bytes() == b""
    else:
        assert list(tmp_path.iterdir()) == []


def test_http_error_survives_cleanup_and_artifact_write_failure(
    runtime_transport, monkeypatch, tmp_path
):
    primary = HTTPError(
        "https://example.snowflakecomputing.com", 403, "forbidden", {}, runtime_transport.response
    )
    runtime_transport.close_errors = {
        name: OSError(f"close {name}") for name in ("response", "cursor", "connection")
    }

    def reject_request(request, timeout):
        raise primary

    def fail_write(*args):
        raise OSError("disk full")

    monkeypatch.setattr("dbt_cortex_agent.invoke.urlopen", reject_request)
    monkeypatch.setattr("dbt_cortex_agent.invoke.write_raw_events", fail_write)
    with pytest.raises(AgentInvocationError, match="HTTP Error 403") as failure:
        invoke_agent("DB", "S", "A", "question", "conn", raw_event_path=tmp_path / "events.jsonl")
    assert failure.value.__cause__ is primary
    assert failure.value.result["errors"] == [str(primary), "disk full"]
    assert failure.value.result["metadata"]["cleanup_errors"] == [
        "close response",
        "close cursor",
        "close connection",
    ]
    assert runtime_transport.closed == ["response", "cursor", "connection"]
    assert failure.value.raw_event_path is None
