from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .identifiers import identifier

def parse_sse(lines: Iterable[bytes | str]) -> dict[str, Any]:
    result: dict[str, Any] = {"answer": "", "tool_uses": [], "tool_results": []}
    current_event: str | None = None
    completed = False
    for raw_line in lines:
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        line = line.strip()
        if line.startswith("event: "):
            current_event = line[7:].strip()
            continue
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            completed = True
            break
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Malformed Agent SSE JSON: {data!r}") from exc
        if current_event == "response.tool_use" and parsed.get("name"):
            result["tool_uses"].append(parsed)
        elif current_event == "response.tool_result" and "content" in parsed:
            result["tool_results"].append(parsed["content"])
        elif current_event == "response.text.delta":
            result["answer"] += parsed.get("text", "")
        elif current_event == "response.text" and not result["answer"]:
            result["answer"] = parsed.get("text", "")
    if not completed:
        raise RuntimeError("Agent SSE stream ended before [DONE]")
    return result


def invoke_agent(
    database: str,
    schema: str,
    agent_name: str,
    question: str,
    connection: str,
    endpoint: str | None = None,
    timeout: float = 60,
) -> dict[str, Any]:
    database = identifier(database, "database")
    schema = identifier(schema, "schema")
    agent_name = identifier(agent_name, "Agent object")
    try:
        import snowflake.connector
    except ImportError as exc:
        raise RuntimeError(
            "Direct invocation requires the 'runtime' extra: pip install 'dbt-cortex-agent[runtime]'"
        ) from exc

    conn = snowflake.connector.connect(connection_name=connection)
    cursor = conn.cursor()
    try:
        if endpoint is None:
            cursor.execute("SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME()")
            organization, account = cursor.fetchone()
            endpoint = (
                f"https://{str(organization).lower()}-"
                f"{str(account).replace('_', '-').lower()}.snowflakecomputing.com"
            )
        parsed_endpoint = urlparse(endpoint)
        hostname = (parsed_endpoint.hostname or "").lower()
        if parsed_endpoint.scheme != "https" or not (
            hostname == "snowflakecomputing.com"
            or hostname.endswith(".snowflakecomputing.com")
        ):
            raise ValueError(
                "Agent endpoint must use HTTPS on a snowflakecomputing.com host"
            )
        token = conn.rest.token
        url = (
            f"{endpoint.rstrip('/')}/api/v2/databases/{quote(database, safe='')}/"
            f"schemas/{quote(schema, safe='')}/agents/{quote(agent_name, safe='')}:run"
        )
        payload = json.dumps(
            {"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}]}
        ).encode("utf-8")
        request = Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Authorization": f'Snowflake Token="{token}"',
            },
            method="POST",
        )
        if timeout <= 0:
            raise ValueError("Agent invocation timeout must be positive")
        with urlopen(request, timeout=timeout) as response:
            return parse_sse(response)
    finally:
        cursor.close()
        conn.close()


def smoke_skills(
    skills: list,
    *,
    database: str,
    schema: str,
    agent_names: dict[str, str],
    connection: str,
    endpoint: str | None = None,
    invoker=invoke_agent,
) -> list[str]:
    verified: list[str] = []
    for skill in skills:
        if skill.agent_name not in agent_names:
            raise ValueError(f"No physical Agent mapping for {skill.agent_name!r}")
        result = invoker(
            database,
            schema,
            agent_names[skill.agent_name],
            f"Use the {skill.skill_name} skill and summarize the expected next actions.",
            connection,
            endpoint,
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
