from __future__ import annotations

import json
import time
from collections.abc import Iterable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .domain import finite_number, is_controlled_operation_error, managed_resource
from .identifiers import identifier

MAX_RESULT_PREVIEW_ROWS = 5
MAX_RAW_EVENT_BYTES = 1_000_000
MAX_STREAM_BYTES = 1_000_000
MAX_AGENT_EVENTS = 10_000


@dataclass(frozen=True)
class AgentEvent:
    event: str
    data: dict[str, Any]


@dataclass
class AgentRunResult:
    answer: str = ""
    tool_uses: list[dict[str, Any]] = field(default_factory=list)
    sql_queries: list[str] = field(default_factory=list)
    result_summaries: list[dict[str, Any]] = field(default_factory=list)
    charts: list[dict[str, Any]] = field(default_factory=list)
    annotations: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "tool_uses": self.tool_uses,
            "sql_queries": self.sql_queries,
            "result_summaries": self.result_summaries,
            "charts": self.charts,
            "annotations": self.annotations,
            "errors": self.errors,
            "metadata": self.metadata,
            "duration_seconds": self.duration_seconds,
        }


class AgentInvocationError(RuntimeError):
    def __init__(self, message: str, result: dict[str, Any]) -> None:
        super().__init__(message)
        self.result = result
        self.raw_event_path: Path | None = None


TERMINAL_EVENTS = frozenset({"done", "response"})


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Agent invocation deadline exceeded")
    return remaining


def _bounded_lines(lines: Iterable[bytes | str], deadline: float | None) -> Iterator[bytes | str]:
    iterator = iter(lines)
    total = 0
    while True:
        if deadline is not None:
            _remaining(deadline)
        if hasattr(lines, "readline"):
            raw_line = lines.readline(MAX_STREAM_BYTES - total + 1)
        else:
            try:
                raw_line = next(iterator)
            except StopIteration:
                if deadline is not None:
                    _remaining(deadline)
                return
        if deadline is not None:
            _remaining(deadline)
        if not raw_line and hasattr(lines, "readline"):
            return
        total += len(raw_line if isinstance(raw_line, bytes) else raw_line.encode("utf-8"))
        if total > MAX_STREAM_BYTES:
            raise RuntimeError(f"Agent SSE stream exceeds {MAX_STREAM_BYTES} byte limit")
        yield raw_line


def _encode_event(event: AgentEvent) -> bytes:
    return (json.dumps({"event": event.event, "data": event.data}, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def frame_sse(
    lines: Iterable[bytes | str], *, deadline: float | None = None
) -> Iterator[AgentEvent]:
    total = 0
    for count, event in enumerate(_frame_sse(_bounded_lines(lines, deadline)), start=1):
        if count > MAX_AGENT_EVENTS:
            raise RuntimeError(f"Agent SSE stream exceeds {MAX_AGENT_EVENTS} event limit")
        total += len(_encode_event(event))
        if total > MAX_RAW_EVENT_BYTES:
            raise RuntimeError(f"Raw Agent event artifact exceeds {MAX_RAW_EVENT_BYTES} byte limit")
        yield event


def _decode_line(raw_line: bytes | str) -> str:
    line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
    return line.rstrip("\r\n")


def _frame_event(event_name: str | None, data_lines: list[str]) -> AgentEvent | None:
    if not data_lines:
        return None
    payload = "\n".join(data_lines)
    if payload == "[DONE]":
        return AgentEvent("done", {})
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Malformed Agent SSE JSON: {payload[:500]!r}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Agent SSE event data must be a JSON object")
    return AgentEvent(event_name or "message", value)


def _frame_sse(lines: Iterable[bytes | str]) -> Iterator[AgentEvent]:  # noqa: C901
    current_event: str | None = None
    data_lines: list[str] = []
    completed = False

    for raw_line in lines:
        line = _decode_line(raw_line)
        if line.startswith(":"):
            continue
        if not line:
            event = _frame_event(current_event, data_lines)
            current_event, data_lines = None, []
            if event:
                yield event
                if event.event in TERMINAL_EVENTS:
                    completed = True
                    break
            continue
        if line.startswith("event:"):
            event = _frame_event(current_event, data_lines)
            data_lines = []
            if event:
                yield event
                if event.event in TERMINAL_EVENTS:
                    completed = True
                    break
            current_event = line[6:].strip()
            continue
        if line.startswith("data:"):
            value = line[5:].lstrip()
            if value != "[DONE]":
                data_lines.append(value)
                continue
            event = _frame_event(current_event, data_lines)
            data_lines = []
            if event:
                yield event
            completed = True
            yield AgentEvent("done", {})
            break

    if not completed and data_lines:
        event = _frame_event(current_event, data_lines)
        if event:
            completed = event.event in TERMINAL_EVENTS
            yield event
    if not completed:
        raise RuntimeError("Agent SSE stream ended before [DONE]")


def _result_summary(result_set: object) -> dict[str, Any]:
    if not isinstance(result_set, dict):
        return {"row_count": 0, "column_count": 0, "preview": []}
    rows = result_set.get("data")
    rows = rows if isinstance(rows, list) else []
    metadata = result_set.get("resultSetMetaData")
    row_type = metadata.get("rowType") if isinstance(metadata, dict) else []
    row_type = row_type if isinstance(row_type, list) else []
    columns = [item.get("name") for item in row_type if isinstance(item, dict)]
    return {
        "row_count": len(rows),
        "column_count": len(columns) or (len(rows[0]) if rows and isinstance(rows[0], list) else 0),
        "columns": columns,
        "preview": rows[:MAX_RESULT_PREVIEW_ROWS],
        "truncated": len(rows) > MAX_RESULT_PREVIEW_ROWS,
    }


def _apply_text_event(result: AgentRunResult, data: dict[str, Any]) -> None:
    result.answer += str(data.get("text") or "")
    annotations = data.get("annotations")
    if isinstance(annotations, list):
        result.annotations.extend(item for item in annotations if isinstance(item, dict))


def _apply_final_response(result: AgentRunResult, data: dict[str, Any]) -> None:
    if data.get("status") not in {None, "completed"}:
        result.errors.append(f"Agent ended in {data.get('status')}")
    content = data.get("content")
    content = content if isinstance(content, list) else []
    final_text = "\n".join(
        str(item.get("text"))
        for item in content
        if isinstance(item, dict) and item.get("type") == "text" and item.get("text")
    )
    if final_text:
        result.answer = final_text
    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        result.metadata.update(metadata)
    warnings = data.get("warnings")
    if isinstance(warnings, list):
        result.metadata["warnings"] = warnings


def _apply_tool_result(result: AgentRunResult, data: dict[str, Any]) -> None:
    content = data.get("content")
    if not isinstance(content, list):
        return
    for value in content:
        payload = value.get("json") if isinstance(value, dict) else None
        if not isinstance(payload, dict):
            continue
        if payload.get("sql"):
            result.sql_queries.append(str(payload["sql"]))
        if payload.get("result_set") is not None:
            result.result_summaries.append(_result_summary(payload["result_set"]))


def _apply_chart(result: AgentRunResult, data: dict[str, Any]) -> None:
    chart = data.get("chart_spec")
    if not isinstance(chart, (dict, str)):
        return
    try:
        result.charts.append(json.loads(chart) if isinstance(chart, str) else chart)
    except json.JSONDecodeError as exc:
        result.errors.append(f"Malformed chart specification: {exc}")


def _apply_metadata(result: AgentRunResult, data: dict[str, Any]) -> None:
    metadata = data.get("metadata", data)
    if isinstance(metadata, dict):
        result.metadata.update(metadata)


def collect_agent_events(
    events: Iterable[AgentEvent],
    *,
    result: AgentRunResult | None = None,
    raw_events: list[AgentEvent] | None = None,
) -> AgentRunResult:
    result = result if result is not None else AgentRunResult()
    for item in events:
        if raw_events is not None:
            raw_events.append(item)
        event, data = item.event, item.data
        if event in {"response.text.delta", "response.text"}:
            _apply_text_event(result, data)
        elif event == "response":
            _apply_final_response(result, data)
        elif event == "response.tool_use" and data.get("name"):
            result.tool_uses.append(data)
        elif event == "response.tool_result":
            _apply_tool_result(result, data)
        elif event == "response.chart":
            _apply_chart(result, data)
        elif event == "response.text.annotation":
            result.annotations.append(data)
        elif event in {"response.error", "error"}:
            result.errors.append(str(data.get("message") or data.get("error") or "Agent error"))
        elif event == "metadata":
            _apply_metadata(result, data)
    if result.errors:
        raise RuntimeError("; ".join(result.errors))
    return result


def parse_sse(lines: Iterable[bytes | str]) -> dict[str, Any]:
    return collect_agent_events(frame_sse(lines)).to_dict()


def write_raw_events(events: list[AgentEvent], target: Path) -> Path:
    encoded = b"".join(_encode_event(event) for event in events)
    if len(encoded) > MAX_RAW_EVENT_BYTES:
        raise ValueError(f"Raw Agent event artifact exceeds {MAX_RAW_EVENT_BYTES} byte limit")
    target = target.resolve()
    if target.exists():
        raise FileExistsError(f"Raw Agent event artifact already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as artifact:
        artifact.write(encoded)
    return target


def compact_agent_output(result: dict[str, Any]) -> str:
    lines = [str(result.get("answer") or "(Agent returned no answer text.)")]
    tools = [str(item.get("name")) for item in result.get("tool_uses", []) if item.get("name")]
    if tools:
        lines.append("Tools: " + ", ".join(dict.fromkeys(tools)))
    if result.get("sql_queries"):
        lines.append(f"SQL statements: {len(result['sql_queries'])}")
    summaries = result.get("result_summaries") or []
    if summaries:
        rows = sum(int(item.get("row_count", 0)) for item in summaries)
        lines.append(f"Result sets: {len(summaries)} ({rows} rows)")
    metadata = result.get("metadata") or {}
    if metadata.get("resolved_version"):
        lines.append(f"Version: {metadata['resolved_version']}")
    if result.get("duration_seconds"):
        lines.append(f"Duration: {result['duration_seconds']:.2f}s")
    if result.get("errors"):
        lines.append("Errors: " + "; ".join(result["errors"]))
    return "\n".join(lines)


def invoke_agent(
    database: str,
    schema: str,
    agent_name: str,
    question: str,
    connection: str,
    endpoint: str | None = None,
    timeout: float = 60,
    role: str | None = None,
    raw_event_path: Path | None = None,
) -> dict[str, Any]:
    database = identifier(database, "database")
    schema = identifier(schema, "schema")
    version_selector = None
    if "!" in agent_name:
        agent_name, version_selector = agent_name.rsplit("!", 1)
        version_selector = identifier(version_selector, "Agent version selector")
    agent_name = identifier(agent_name, "Agent object")
    try:
        import snowflake.connector
    except ImportError as exc:
        raise RuntimeError(
            "Direct invocation requires the 'runtime' extra: "
            "pip install 'dbt-cortex-agent[runtime]'"
        ) from exc
    timeout = finite_number(timeout, "Agent invocation timeout")
    if timeout <= 0:
        raise ValueError("Agent invocation timeout must be positive")
    if raw_event_path is not None and raw_event_path.exists():
        raise FileExistsError(f"Raw Agent event artifact already exists: {raw_event_path}")
    if endpoint is not None:
        _validate_endpoint(endpoint)

    start = time.monotonic()
    deadline = start + timeout
    result = AgentRunResult(
        metadata={
            "requested_version": version_selector,
            "agent_fqn": f"{database}.{schema}.{agent_name}",
        }
    )
    events: list[AgentEvent] = []
    failure: Exception | None = None
    try:
        with ExitStack() as resources:
            conn = resources.enter_context(
                managed_resource(
                    snowflake.connector.connect(
                        connection_name=connection,
                        login_timeout=_remaining(deadline),
                        network_timeout=_remaining(deadline),
                        socket_timeout=_remaining(deadline),
                    )
                )
            )
            _remaining(deadline)
            cursor = resources.enter_context(managed_resource(conn.cursor()))
            if endpoint is None:
                cursor.execute(
                    "SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME()",
                    timeout=_remaining(deadline),
                )
                organization, account = cursor.fetchone()
                endpoint = (
                    f"https://{str(organization).lower()}-"
                    f"{str(account).replace('_', '-').lower()}.snowflakecomputing.com"
                )
            request = _agent_request(
                endpoint,
                database,
                schema,
                agent_name,
                version_selector,
                question,
                conn.rest.token,
                role,
            )
            try:
                response = urlopen(request, timeout=_remaining(deadline))
            except HTTPError as exc:
                resources.enter_context(managed_resource(exc))
                raise
            resources.enter_context(managed_resource(response))
            collect_agent_events(
                frame_sse(response, deadline=deadline), result=result, raw_events=events
            )
            _remaining(deadline)
    except Exception as exc:
        if not is_controlled_operation_error(exc) and not isinstance(exc, HTTPException):
            raise
        failure = exc
        if str(exc) not in result.errors:
            result.errors.append(str(exc))
        cleanup_errors = getattr(exc, "cleanup_errors", [])
        if cleanup_errors:
            result.metadata["cleanup_errors"] = [str(error) for error in cleanup_errors]
    result.duration_seconds = round(time.monotonic() - start, 3)
    result.metadata.update(
        {
            "requested_version": version_selector,
            "agent_fqn": f"{database}.{schema}.{agent_name}",
        }
    )
    return _finish_invocation(result, events, raw_event_path, failure)


def _finish_invocation(
    result: AgentRunResult,
    events: list[AgentEvent],
    raw_event_path: Path | None,
    failure: Exception | None,
) -> dict[str, Any]:
    artifact_path = None
    try:
        if raw_event_path is not None:
            artifact_path = write_raw_events(events, raw_event_path)
    except Exception as exc:
        if not is_controlled_operation_error(exc):
            raise
        result.errors.append(str(exc))
        failure = failure if failure is not None else exc
    if failure is not None:
        error = AgentInvocationError(str(failure), result.to_dict())
        error.raw_event_path = artifact_path
        raise error from failure
    return result.to_dict()


def _agent_request(
    endpoint: str,
    database: str,
    schema: str,
    agent_name: str,
    version_selector: str | None,
    question: str,
    token: str,
    role: str | None,
) -> Request:
    _validate_endpoint(endpoint)
    agent_path = f"agents/{quote(agent_name, safe='')}"
    if version_selector:
        agent_path += f"/versions/{quote(version_selector, safe='')}"
    url = (
        f"{endpoint.rstrip('/')}/api/v2/databases/{quote(database, safe='')}/"
        f"schemas/{quote(schema, safe='')}/{agent_path}:run"
    )
    payload = json.dumps(
        {"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}]}
    ).encode("utf-8")
    return Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f'Snowflake Token="{token}"',
            **({"X-Snowflake-Role": identifier(role, "Agent runtime role")} if role else {}),
        },
        method="POST",
    )


def _validate_endpoint(endpoint: str) -> None:
    parsed_endpoint = urlparse(endpoint)
    hostname = (parsed_endpoint.hostname or "").lower()
    if parsed_endpoint.scheme != "https" or not (
        hostname == "snowflakecomputing.com" or hostname.endswith(".snowflakecomputing.com")
    ):
        raise ValueError("Agent endpoint must use HTTPS on a snowflakecomputing.com host")


def smoke_skills(
    skills: list,
    *,
    agent_names: dict[str, dict[str, str]],
    connection: str,
    endpoint: str | None = None,
    invoker=invoke_agent,
    role: str | None = None,
) -> list[str]:
    verified: list[str] = []
    for skill in skills:
        if skill.agent_name not in agent_names:
            raise ValueError(f"No physical Agent mapping for {skill.agent_name!r}")
        identity = agent_names[skill.agent_name]
        result = invoker(
            identity["database"],
            identity["schema"],
            identity["object_name"],
            f"Use the {skill.skill_name} skill and summarize the expected next actions.",
            connection,
            endpoint,
            **({"role": role} if role is not None else {}),
        )
        selected = any(
            item.get("name") == "server_skill"
            and (item.get("input") or {}).get("skill_name") == skill.skill_name
            for item in result.get("tool_uses", [])
        )
        if not selected:
            raise RuntimeError(
                f"Skill smoke failed for {skill.skill_name!r}: server_skill was not selected"
            )
        verified.append(skill.skill_name)
    return verified
