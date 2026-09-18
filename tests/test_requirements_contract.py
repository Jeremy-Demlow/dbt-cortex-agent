from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
ACTIVE_REQUIREMENTS = range(21, 33)
MAP_PATH = ROOT / "tests/requirement_evidence.json"


def _requirement_path(number: int) -> Path:
    matches = tuple((ROOT / "requirements").glob(f"REQ-{number:03d}_*.md"))
    assert len(matches) == 1, f"REQ-{number:03d} must have exactly one tracked file"
    return matches[0]


def test_active_requirements_are_indexed_and_linked() -> None:
    index = (ROOT / "requirements/README.md").read_text(encoding="utf-8")
    stories = (ROOT / "requirements/user_stories.md").read_text(encoding="utf-8")
    cases = (ROOT / "tests/test_cases.md").read_text(encoding="utf-8")

    for number in ACTIVE_REQUIREMENTS:
        requirement = _requirement_path(number)
        prefix = f"REQ-{number:03d}"
        assert requirement.name in index
        assert f"## {prefix}" in stories
        assert f"## {prefix}:" in cases


def test_every_active_acceptance_criterion_has_a_test_case() -> None:
    cases = (ROOT / "tests/test_cases.md").read_text(encoding="utf-8")

    for number in ACTIVE_REQUIREMENTS:
        text = _requirement_path(number).read_text(encoding="utf-8")
        acceptance = text.split("## Acceptance Criteria", 1)[1].split("\n## ", 1)[0]
        criterion_numbers = [int(value) for value in re.findall(r"(?m)^(\d+)\. ", acceptance)]
        assert criterion_numbers == list(range(1, len(criterion_numbers) + 1))
        for criterion in criterion_numbers:
            assert f"TC-{number:03d}-{criterion:02d}" in cases


def _expected_criteria():
    expected = set()
    for number in ACTIVE_REQUIREMENTS:
        text = _requirement_path(number).read_text(encoding="utf-8")
        acceptance = text.split("## Acceptance Criteria", 1)[1].split("\n## ", 1)[0]
        criterion_count = len(re.findall(r"(?m)^\d+\. ", acceptance))
        assert criterion_count, f"REQ-{number:03d} has no acceptance criteria"
        for criterion in range(1, criterion_count + 1):
            expected.add(f"TC-{number:03d}-{criterion:02d}")
    return expected


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, f"Duplicate JSON key: {key}"
        result[key] = value
    return result


@pytest.fixture
def evidence_map():
    return json.loads(MAP_PATH.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)


def _strings(values):
    assert isinstance(values, list), "Expected a list"
    assert all(isinstance(value, str) and value.strip() for value in values)
    assert len(values) == len(set(values)), "Duplicate references"


def _local_file(reference, root=ROOT):
    assert isinstance(reference, str) and reference
    path = Path(reference)
    assert not path.is_absolute() and ".." not in path.parts, "Non-local reference"
    assert ":" not in reference and "\\" not in reference, "Non-local reference"
    resolved = (root / path).resolve()
    assert resolved.is_relative_to(root.resolve()), "Reference escapes repository"
    assert resolved.is_file(), f"Missing reference: {reference}"
    return resolved


def _validate_proof(proof):
    assert isinstance(proof, dict)
    kind = proof.get("kind")
    if kind in {"behavioral", "structural"}:
        assert set(proof) == {"kind", "nodes", "scope"}
        _strings(proof["nodes"])
        assert proof["nodes"], "Offline proof requires collected tests"
    elif kind == "live_historic":
        assert set(proof) == {"kind", "report", "scope"}
        _local_file(proof["report"])
    else:
        assert kind == "live_pending", f"Unknown proof kind: {kind}"
        assert set(proof) == {"kind", "scope"}
    assert isinstance(proof["scope"], str) and proof["scope"].strip()


def _validate_map(mapping, expected):
    assert set(mapping) == {"schema_version", "criteria", "proofs", "article", "fixtures"}
    assert type(mapping["schema_version"]) is int and mapping["schema_version"] == 1
    assert isinstance(mapping["criteria"], dict) and set(mapping["criteria"]) == expected
    assert isinstance(mapping["proofs"], dict) and mapping["proofs"]
    for proof in mapping["proofs"].values():
        _validate_proof(proof)
    referenced = set()
    for criterion, entry in mapping["criteria"].items():
        assert set(entry) == {"claim", "proofs", "gaps"}, criterion
        assert isinstance(entry["claim"], str) and entry["claim"].strip(), criterion
        _strings(entry["proofs"])
        _strings(entry["gaps"])
        assert set(entry["proofs"]) <= mapping["proofs"].keys(), criterion
        kinds = {mapping["proofs"][key]["kind"] for key in entry["proofs"]}
        if "behavioral" not in kinds or kinds & {"live_pending", "live_historic"}:
            assert entry["gaps"], (
                f"{criterion}: structural/historical/pending is not complete proof"
            )
        referenced.update(entry["proofs"])
    assert referenced == mapping["proofs"].keys(), "Orphan proof"


def _resolve_node(selector, collect, root=ROOT):
    assert isinstance(selector, str) and "::" in selector, "Concrete test node required"
    filename, _ = selector.split("::", 1)
    path = _local_file(filename, root)
    assert path.suffix == ".py" and path.name.startswith("test_")
    nodes = collect(path)
    assert selector in nodes, f"Uncollected test node: {selector}"
    assert nodes[selector], f"Empty test selector: {selector}"
    return nodes[selector]


def test_evidence_map_schema_and_complete_criterion_inventory(evidence_map):
    _validate_map(evidence_map, _expected_criteria())


def test_offline_proofs_link_to_collected_test_nodes(evidence_map, collected_test_nodes):
    for proof in evidence_map["proofs"].values():
        for selector in proof.get("nodes", []):
            _resolve_node(selector, collected_test_nodes)


def test_article_claims_link_to_requirements_and_bounded_proofs(evidence_map):
    article = evidence_map["article"]
    assert set(article) == {"path", "sections"}
    text = _local_file(article["path"]).read_text(encoding="utf-8")
    headings = set(re.findall(r"(?m)^## (.+)$", text))
    assert set(article["sections"]) == headings
    linked = set()
    for criteria in article["sections"].values():
        _strings(criteria)
        assert criteria and set(criteria) <= evidence_map["criteria"].keys()
        linked.update(criteria)
    assert {f"TC-028-{number:02d}" for number in range(1, 11)} <= linked


def test_incomplete_requirement_statuses_do_not_claim_complete(evidence_map):
    index = (ROOT / "requirements/README.md").read_text(encoding="utf-8")
    for number in ACTIVE_REQUIREMENTS:
        entries = [
            entry
            for key, entry in evidence_map["criteria"].items()
            if key.startswith(f"TC-{number:03d}-")
        ]
        if not any(entry["gaps"] for entry in entries):
            continue
        requirement = _requirement_path(number)
        status = re.search(r"(?m)^\*\*Status:\*\* (.+)$", requirement.read_text()).group(1)
        assert not status.startswith("Complete"), requirement.name
        row = next(line for line in index.splitlines() if f"]({requirement.name})" in line)
        assert not row.split("|")[-2].strip().startswith("Complete"), requirement.name


@pytest.mark.parametrize(
    "selector",
    [
        "tests/test_domain.py::test_nonexistent_proof",
        "tests/test_domain.py::TC-021-01",
        "tests/test_domain.py::test_finite_number_rejects_non_finite_or_non_numeric_values[missing]",
        "tests/test_domain.py",
    ],
)
def test_nonexistent_or_comment_only_linkage_is_rejected(selector, collected_test_nodes):
    with pytest.raises(AssertionError, match="Uncollected|Concrete test node"):
        _resolve_node(selector, collected_test_nodes)


def test_comment_only_module_collects_no_evidence(tmp_path, collected_test_nodes):
    path = tmp_path / "test_comment_only.py"
    path.write_text("# Evidence: TC-028-10\n# def test_claim(): pass\n", encoding="utf-8")
    assert collected_test_nodes(path) == {}
    with pytest.raises(AssertionError, match="Uncollected"):
        _resolve_node("test_comment_only.py::test_claim", collected_test_nodes, tmp_path)


def test_linkage_collection_does_not_execute_test_bodies(tmp_path, collected_test_nodes):
    path = tmp_path / "test_collection_only.py"
    path.write_text(
        "def test_not_executed():\n    raise AssertionError('collection ran test body')\n",
        encoding="utf-8",
    )
    collected = collected_test_nodes(path)
    assert len(collected) == 1
    assert next(iter(collected)).endswith("::test_not_executed")


def test_parameterized_function_link_resolves_all_collected_cases(collected_test_nodes):
    selector = "tests/test_materialization.py::test_materialization_uses_resolved_identity"
    nodes = _resolve_node(selector, collected_test_nodes)
    assert nodes == {f"{selector}[{schema}]" for schema in ("DEV_AGENTS", "CUSTOM_AGENTS", "DEV")}
    for node in nodes:
        assert _resolve_node(node, collected_test_nodes) == {node}


@pytest.mark.parametrize("damage", ["missing", "extra", "orphan", "unknown_proof", "empty_gap"])
def test_evidence_map_rejects_incomplete_or_misleading_inventory(evidence_map, damage):
    mapping = copy.deepcopy(evidence_map)
    if damage == "missing":
        del mapping["criteria"]["TC-028-10"]
    elif damage == "extra":
        mapping["criteria"]["TC-999-01"] = mapping["criteria"]["TC-028-10"]
    elif damage == "orphan":
        mapping["proofs"]["orphan"] = {"kind": "live_pending", "scope": "No live run"}
    elif damage == "unknown_proof":
        mapping["criteria"]["TC-028-10"]["proofs"] = ["not_a_proof"]
    else:
        mapping["criteria"]["TC-025-13"]["gaps"] = []
    with pytest.raises(AssertionError):
        _validate_map(mapping, _expected_criteria())


@pytest.mark.parametrize(
    "proof",
    [
        {"kind": "behavioral", "nodes": [], "scope": "Empty"},
        {"kind": "comment", "nodes": ["TC-028-10"], "scope": "Not a test"},
        {"kind": "live_pending", "nodes": ["tests/test_ci.py"], "scope": "Not live"},
        {"kind": "live_historic", "report": "https://example.com/proof", "scope": "External"},
    ],
)
def test_invalid_proof_schema_is_rejected(proof):
    with pytest.raises(AssertionError):
        _validate_proof(proof)


def test_duplicate_json_keys_are_rejected():
    with pytest.raises(AssertionError, match="Duplicate JSON key"):
        json.loads('{"TC-028-10": {}, "TC-028-10": {}}', object_pairs_hook=_unique_object)


def _compatibility_schema(payload):
    assert isinstance(payload, dict)
    assert set(payload) == {
        "version",
        "top_level_commands",
        "agent_commands",
        "exit_codes",
        "smoke_preview_fields",
        "candidate_schema_version",
        "lifecycle_owner",
        "python_agent_ddl",
        "notes",
    }
    assert isinstance(payload["version"], str)
    assert re.fullmatch(r"\d+\.\d+\.\d+", payload["version"])
    for key in ("top_level_commands", "agent_commands", "smoke_preview_fields", "notes"):
        _strings(payload[key])
        assert payload[key], key
    assert set(payload["exit_codes"]) == {
        "success",
        "quality_or_diagnostic_failure",
        "controlled_error",
    }
    assert all(type(value) is int for value in payload["exit_codes"].values())
    assert type(payload["candidate_schema_version"]) is int
    assert payload["candidate_schema_version"] > 0
    assert payload["lifecycle_owner"] == "dbt materialization"
    assert payload["python_agent_ddl"] is False


def _protocol_schema(text):
    from dbt_cortex_agent.invoke import frame_sse

    events = list(frame_sse(text.splitlines(keepends=True)))
    assert events, "Empty protocol fixture"
    for event in events:
        assert isinstance(event.event, str) and event.event
        assert isinstance(event.data, dict), "Event data must be an object"
        if event.event == "response.tool_use":
            assert isinstance(event.data.get("name"), str) and event.data["name"]
            assert isinstance(event.data.get("input"), dict)
        elif event.event in {"response", "response.tool_result"}:
            content = event.data.get("content")
            assert isinstance(content, list) and all(isinstance(item, dict) for item in content)
            if event.event == "response":
                assert isinstance(event.data.get("metadata", {}), dict)
        elif event.event == "response.chart":
            chart = event.data.get("chart_spec")
            if isinstance(chart, str):
                chart = json.loads(chart)
            assert isinstance(chart, dict)


def _validate_fixtures(mapping):
    fixtures = mapping["fixtures"]
    assert isinstance(fixtures, list) and fixtures
    paths = set()
    for fixture in fixtures:
        assert set(fixture) == {"path", "schema", "proof", "provenance"}
        path = _local_file(fixture["path"])
        assert path.is_relative_to((ROOT / "tests/fixtures").resolve())
        assert fixture["path"] not in paths, "Duplicate fixture"
        paths.add(fixture["path"])
        assert fixture["provenance"] in {"synthetic_local", "unverified_capture"}
        proof = mapping["proofs"].get(fixture["proof"])
        assert proof and proof["kind"] == "behavioral", "Fixture needs behavioral consumer proof"
        text = path.read_text(encoding="utf-8")
        if fixture["schema"] == "compatibility-v1":
            _compatibility_schema(json.loads(text, object_pairs_hook=_unique_object))
        else:
            assert fixture["schema"] == "agent-sse-v1", "Unknown fixture schema"
            _protocol_schema(text)
    assert paths == {
        str(path.relative_to(ROOT))
        for path in (ROOT / "tests/fixtures").rglob("*")
        if path.is_file()
    }, "Every checked-in fixture needs a schema and consumer proof"


def test_fixture_schemas_and_proof_links(evidence_map):
    _validate_fixtures(evidence_map)


@pytest.mark.parametrize("damage", ["missing", "boolean_version", "extra", "wrong_exit", "notes"])
def test_malformed_fixture_shapes_are_rejected(damage):
    payload = json.loads((ROOT / "tests/fixtures/compatibility/0.0.5.json").read_text())
    if damage == "missing":
        del payload["smoke_preview_fields"]
    elif damage == "boolean_version":
        payload["candidate_schema_version"] = True
    elif damage == "extra":
        payload["unexpected"] = "not an allowed field"
    elif damage == "wrong_exit":
        payload["exit_codes"]["success"] = "0"
    else:
        payload["notes"] = "not a list"
    with pytest.raises(AssertionError):
        _compatibility_schema(payload)


@pytest.mark.parametrize(
    "text",
    [
        'event: response.tool_use\ndata: {"name": 7, "input": {}}\n\ndata: [DONE]\n',
        'event: response\ndata: {"status": "completed", "content": {}}\n\n',
        'event: response.chart\ndata: {"chart_spec": "[]"}\n\ndata: [DONE]\n',
        "event: response\ndata: not-json\n\n",
    ],
)
def test_malformed_protocol_fixture_schema_is_rejected(text):
    with pytest.raises((AssertionError, RuntimeError)):
        _protocol_schema(text)


@pytest.mark.parametrize("damage", ["schema", "provenance", "duplicate", "missing", "proof"])
def test_fixture_registry_rejects_invalid_contracts(evidence_map, damage):
    mapping = copy.deepcopy(evidence_map)
    if damage == "duplicate":
        mapping["fixtures"].append(mapping["fixtures"][0])
    elif damage == "missing":
        mapping["fixtures"].pop()
    else:
        mapping["fixtures"][0][damage] = "unknown"
    with pytest.raises(AssertionError):
        _validate_fixtures(mapping)


@pytest.mark.parametrize("reference", ["../outside", "/tmp/outside", "https://example.com/proof"])
def test_nonlocal_evidence_references_are_rejected(reference):
    with pytest.raises(AssertionError, match="Non-local"):
        _local_file(reference)


def test_private_preview_features_do_not_become_scaffold_options() -> None:
    requirement = _requirement_path(24).read_text(encoding="utf-8")

    assert "does not require a Semantic View" in requirement
    assert "no private-preview key receives a package-specific CLI option" in requirement
    assert "Cortex Sense-specific CLI flags" in requirement
