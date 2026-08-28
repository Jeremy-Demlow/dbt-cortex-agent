from __future__ import annotations

import json
import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

# Evidence: TC-021-02 TC-021-09 TC-023-03
from dbt_cortex_agent.domain import AgentVersionSelector, VersionKind, finite_number
from dbt_cortex_agent.identifiers import fqn, identifier, stage_path, version
from dbt_cortex_agent.invoke import frame_sse

SAFE_IDENTIFIER = st.from_regex(r"[A-Za-z_][A-Za-z0-9_$]{0,30}", fullmatch=True)
SAFE_PATH_PART = st.from_regex(r"[A-Za-z0-9_$-][A-Za-z0-9_$.-]{0,20}", fullmatch=True).filter(
    lambda value: value not in {".", ".."}
)


@given(SAFE_IDENTIFIER)
def test_identifier_property_normalizes_and_is_idempotent(value: str) -> None:
    normalized = identifier(value)
    assert normalized == value.upper()
    assert identifier(normalized) == normalized


@given(st.lists(SAFE_IDENTIFIER, min_size=3, max_size=3))
def test_fqn_property_normalizes_each_component(parts: list[str]) -> None:
    normalized = fqn(".".join(parts), "object")
    assert normalized.split(".") == [part.upper() for part in parts]


@given(st.integers(min_value=1, max_value=10**12))
def test_version_property_round_trips_positive_versions(number: int) -> None:
    expected = f"VERSION${number}"
    assert version(expected.lower()) == expected
    selector = AgentVersionSelector.parse(expected.lower())
    assert selector == AgentVersionSelector(expected, VersionKind.COMMITTED)


@given(
    SAFE_IDENTIFIER,
    SAFE_IDENTIFIER,
    SAFE_IDENTIFIER,
    st.lists(SAFE_PATH_PART, min_size=1, max_size=5),
)
def test_stage_path_property_returns_safe_normalized_parts(
    database: str, schema: str, stage: str, suffix: list[str]
) -> None:
    raw = f"@{database}.{schema}.{stage}/{'/'.join(suffix)}"
    stage_name, normalized_suffix = stage_path(raw)
    assert stage_name == f"{database}.{schema}.{stage}".upper()
    assert normalized_suffix == "/".join(suffix)
    assert ".." not in normalized_suffix.split("/")


@given(st.one_of(st.floats(allow_nan=False, allow_infinity=False), st.integers()))
def test_finite_number_property_accepts_exactly_finite_numbers(value: float | int) -> None:
    assert math.isfinite(finite_number(value, "number"))


@given(st.sampled_from(["DEFAULT", "FIRST", "LAST", "LIVE"]))
def test_reserved_selector_property_never_classifies_as_alias(value: str) -> None:
    assert AgentVersionSelector.parse(value.lower()).kind is VersionKind.SHORTCUT


@given(st.text(min_size=1).filter(lambda value: "\n" not in value and "\r" not in value))
def test_identifier_property_never_returns_unsafe_input(value: str) -> None:
    try:
        normalized = identifier(value)
    except ValueError:
        return
    assert normalized == value.upper()
    assert all(character.isalnum() or character in "_$" for character in normalized)
    assert normalized[0].isalpha() or normalized[0] == "_"


@given(st.text(max_size=100))
def test_stage_path_property_never_returns_traversal(value: str) -> None:
    try:
        _, suffix = stage_path(value)
    except ValueError:
        return
    assert all(part not in {"", ".", ".."} for part in suffix.split("/"))


@given(
    st.text(max_size=100),
    st.booleans(),
)
def test_sse_framing_property_is_invariant_to_text_or_bytes(answer: str, use_bytes: bool) -> None:
    payload = json.dumps({"status": "completed", "content": [{"type": "text", "text": answer}]})
    text_lines = ["event: response\n", f"data: {payload}\n", "\n"]
    lines = [line.encode() for line in text_lines] if use_bytes else text_lines
    events = list(frame_sse(lines))
    assert events[0].event == "response"
    assert events[0].data["content"][0]["text"] == answer


@given(st.lists(st.text(max_size=50), min_size=0, max_size=5))
def test_unterminated_sse_property_always_fails(deltas: list[str]) -> None:
    lines: list[str] = []
    for delta in deltas:
        lines.extend(
            ["event: response.text.delta\n", f"data: {json.dumps({'text': delta})}\n", "\n"]
        )
    with pytest.raises(RuntimeError, match="ended before"):
        list(frame_sse(lines))
