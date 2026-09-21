import json
import re
import shlex
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

# Evidence: TC-022-12 TC-024-10 TC-028-02 TC-028-09
import pytest
import yaml
from test_eval_verify import _candidate, _plan

from dbt_cortex_agent import __version__
from dbt_cortex_agent.cli import build_parser, main
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.init import STARTER_PATHS
from dbt_cortex_agent.manifest import cortex_agents, skill_declarations

ROOT = Path(__file__).parents[1]
SKILL = ROOT / ".cortex/skills/dbt-cortex-agent-project/SKILL.md"
TEXT = SKILL.read_text(encoding="utf-8")
COMMANDS = [
    shlex.split(line)
    for block in re.findall(r"^```bash\n(.*?)^```", TEXT, re.MULTILINE | re.DOTALL)
    for line in block.replace("\\\n", " ").splitlines()
    if line.strip().startswith("dbt-cortex-agent ")
]


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "dbt_cortex_agent.cli.resolve_config", lambda args: resolve_config(args, {})
    )
    for boundary in ("subprocess.Popen", "socket.socket.connect", "socket.create_connection"):
        monkeypatch.setattr(
            boundary, lambda *args, **kwargs: pytest.fail("unexpected external I/O")
        )


@pytest.fixture
def values(tmp_path):
    return {
        "PROJECT_DIR": str(tmp_path / "consumer project"),
        "AGENT": "agent",
        "MODEL": "sem_orders",
        "TARGET": "sandbox",
        "DATABASE": "DB",
        "PACKAGE_GIT_URL": "https://example.invalid/dbt-cortex-agent.git",
        "PACKAGE_TAG": f"v{__version__}",
        "SUITE": "core",
        "BASELINE_DIR": str(tmp_path / "chosen baselines"),
        "CANDIDATE_JSON": str(tmp_path / "exact candidate.json"),
        "CONNECTION": "offline",
        "ROLE": "REVIEWED_ROLE",
        "WAREHOUSE": "WH",
        "AGENT_SCHEMA": "AGENTS",
        "VERSION": "VERSION$2",
        "QUESTION": "What can you do?",
        "TOOL": "GovernedAnalytics",
        "ALIAS": "production",
    }


def _argv(tokens, values):
    return [re.sub(r"<([A-Z_]+)>", lambda match: values[match[1]], token) for token in tokens[1:]]


def _command(prefix, values, *, apply=False, semantic=False):
    matches = [
        tokens
        for tokens in COMMANDS
        if tokens[1 : 1 + len(prefix.split())] == prefix.split()
        and ("--apply" in tokens) == apply
        and ("--semantic-view-model" in tokens) == semantic
    ]
    assert len(matches) == 1, (prefix, matches)
    return _argv(matches[0], values)


def _run(argv, capsys, code=0):
    assert main(argv) == code
    captured = capsys.readouterr()
    return json.loads(captured.err if code == 2 else captured.out)


def _snapshot(directory):
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _project(values):
    project = Path(values["PROJECT_DIR"])
    project.mkdir()
    (project / "dbt_project.yml").write_text(
        "name: consumer\nversion: 1.0.0\nconfig-version: 2\nvars:\n  existing: keep\n"
    )
    return project


def _render(source, macro_harness, name="agent"):
    config, refs = {}, []
    semantic = {
        "resource_type": "model",
        "name": "sem_orders",
        "database": "DATA_DB",
        "schema": "RESOLVED_SEMANTIC",
        "alias": "NAMED_VIEW",
        "config": {"materialized": "semantic_view"},
    }
    macro_harness.context.update(
        config=lambda **kwargs: config.update(kwargs) or "",
        ref=lambda model: refs.append(model) or "REF_MUST_NOT_LEAK",
        var=lambda key, default=None: default,
        env_var=lambda key, default=None: default,
        target=SimpleNamespace(name="sandbox", database="DB", warehouse="WH"),
        graph=SimpleNamespace(nodes={"model.consumer.sem_orders": semantic}),
    )
    rendered = macro_harness.environment.from_string(source).render(macro_harness.context)
    spec = macro_harness.call("cortex_agent__materialization_spec", rendered, name)
    node = {
        "name": name,
        "unique_id": f"model.consumer.{name}",
        "resource_type": "model",
        "database": config["database"],
        "schema": "RESOLVED_AGENTS",
        "alias": config["alias"],
        "config": config,
        "compiled_code": rendered,
    }
    assert "REF_MUST_NOT_LEAK" not in rendered
    assert cortex_agents({"nodes": {node["unique_id"]: node}})[0]["physical_fqn"] == (
        f"DB.RESOLVED_AGENTS.{config['alias']}"
    )
    return spec, node, refs


def test_project_skill_is_single_file_and_release_aware():
    frontmatter = yaml.safe_load(TEXT.split("---", 2)[1])
    assert frontmatter["name"] == "dbt-cortex-agent-project"
    assert len(TEXT.splitlines()) < 500
    assert not (SKILL.parent / "scripts").exists()


def test_project_skill_preserves_materialization_ownership():
    text = TEXT
    assert f"This workflow targets `{__version__}`" in text
    assert "materialized='cortex_agent'" in text or "materialized: cortex_agent" in text
    for removed in ("dbt-cortex-agent agent render", "dbt-cortex-agent agent grant"):
        assert removed not in text
    assert "only Agent\n  deployment authority" in text
    assert "Infrastructure and grants are adopter-owned" in text
    assert "Fresh parse does not render arbitrary Jinja" in text
    for obsolete in ("exposures:", "Define each Agent as an exposure", "--no-parse"):
        assert obsolete not in text


def test_project_skill_uses_composed_package_workflows_without_wrappers():
    text = TEXT
    for obsolete in (
        "dbt-cortex-agent eval run",
        "project_runner.py",
        "agent_gate.py",
        "make dbt-focus",
    ):
        assert obsolete not in text


def test_project_skill_keeps_separate_approval_boundaries():
    text = TEXT
    stops = ("STOP 1", "STOP 2", "STOP 3", "STOP 4")
    positions = [text.index(stop) for stop in stops]
    assert positions == sorted(positions)
    for number in range(1, 5):
        section = text.split(f"## STOP {number}", 1)[1].split("\n### ", 1)[0]
        assert "explicitly approves" in section
        assert "Resume only" in section
        assert "stop again" in section
    assert "Passing package tests does not prove skill routing" in text
    assert "Paid-run approval does not satisfy this stop" in text
    lifecycle = text.split("#### F.")[1].split("### 4.")[0]
    assert "STOP 1 packet for fresh-parse artifacts" in lifecycle
    assert "proceed to Step 6 after that approval" in lifecycle


@pytest.mark.parametrize("tokens", COMMANDS, ids=lambda tokens: " ".join(tokens[1:3]))
def test_every_fenced_package_command_parses(tokens, values):
    args = build_parser().parse_args(_argv(tokens, values))
    assert callable(args.handler)
    assert args.json is True
    assert not args.no_parse


@pytest.mark.parametrize("semantic", [False, True], ids=["route_a", "route_b"])
def test_skill_scaffold_preview_apply_and_native_discovery(semantic, values, capsys, macro_harness):
    project = _project(values)
    preview = _command("agent scaffold", values, semantic=semantic)
    before = _snapshot(project)
    assert _run(preview, capsys)["applied"] is False
    assert _snapshot(project) == before
    apply = [*preview, "--apply"] if semantic else _command("agent scaffold", values, apply=True)
    assert _run(apply, capsys)["applied"] is True
    model_dir = project / "models/agents/agent"
    metadata = yaml.safe_load((model_dir / "agent.yml").read_text())
    assert metadata["models"][0]["name"] == "agent"
    assert "exposures" not in metadata
    spec, node, refs = _render((model_dir / "agent.sql").read_text(), macro_harness)
    assert refs == (["sem_orders"] if semantic else [])
    assert not (model_dir / "evals").exists()
    if semantic:
        assert spec["tools"][0]["tool_spec"]["name"] == "GovernedAnalytics"
        assert spec["tool_resources"]["GovernedAnalytics"]["semantic_view"] == (
            "DATA_DB.RESOLVED_SEMANTIC.NAMED_VIEW"
        )
    else:
        assert "tools" not in spec and "tool_resources" not in spec


def test_skill_orders_preview_apply_in_temporary_project(values, capsys, macro_harness):
    project = _project(values)
    before = _snapshot(project)
    preview = _run(_command("init", values), capsys)
    assert preview["changed_files"] == []
    assert _snapshot(project) == before
    result = _run(_command("init", values, apply=True), capsys)
    assert {str(Path(path).relative_to(project)) for path in result["changed_files"]} == {
        *STARTER_PATHS,
        "packages.yml",
        "dbt_project.yml",
        ".dbtignore",
    }
    packages = yaml.safe_load((project / "packages.yml").read_text())["packages"]
    assert packages[0] == {"git": values["PACKAGE_GIT_URL"], "revision": values["PACKAGE_TAG"]}
    assert packages[1]["package"] == "Snowflake-Labs/dbt_semantic_view"
    variables = yaml.safe_load((project / "dbt_project.yml").read_text())["vars"]
    assert variables["existing"] == "keep"
    assert variables["cortex_agent_allowed_targets"] == ["sandbox"]
    assert variables["cortex_agent_allowed_databases"] == ["DB"]
    assert "models/agents/*/skills/**" in (project / ".dbtignore").read_text()
    model = project / "models/agents/orders_assistant/orders_assistant.sql"
    spec, _, refs = _render(model.read_text(), macro_harness, "orders_assistant")
    assert refs == ["sem_orders"]
    assert spec["tool_resources"]["OrdersAnalytics"]["semantic_view"] == "DB.SEMANTIC.SEM_ORDERS"
    assert _run(_command("init", values, apply=True), capsys)["changed_files"] == []


def test_skill_migration_contract_matches_native_specimens(macro_harness, tmp_path):
    route = TEXT.split("#### D.")[1].split("#### E.")[0]
    assert "config.meta.agent_display_name" in route
    assert "config.meta.cortex_agent.skills" in route
    assert "never mutate it during discovery or authoring" in route
    source = (
        ROOT / "integration_tests/models/agents/enterprise_compatibility_probe.sql"
    ).read_text()
    helper = (ROOT / "integration_tests/macros/enterprise_compatibility.sql").read_text()
    module = macro_harness.environment.from_string(helper).make_module(macro_harness.context)
    macro_harness.context["enterprise_compatibility_orchestration_instructions"] = (
        module.enterprise_compatibility_orchestration_instructions
    )
    spec, node, _ = _render(source, macro_harness)
    assert node["config"]["meta"]["agent_display_name"] == "Enterprise Compatibility Probe"
    assert node["config"]["meta"]["agent_comment"]
    assert node["config"]["meta"]["deploy_alias"] == "latest"
    assert {"skills", "mcp_servers", "instructions", "orchestration"} <= spec.keys()
    manifest = {"nodes": {node["unique_id"]: node}}
    assert (
        skill_declarations(manifest, tmp_path)[0].stage_path == spec["skills"][0]["source"]["path"]
    )
    spec["experimental"] = {"reviewed_setting": {"preserve": True}}
    assert (
        macro_harness.call("cortex_agent__materialization_spec", yaml.safe_dump(spec), "agent")
        == spec
    )
    with pytest.raises(ValueError, match="explicitly define models.orchestration"):
        macro_harness.call("cortex_agent__materialization_spec", "instructions: {}", "agent")


def test_skill_eval_verify_preview_binds_selection_and_baseline(values, capsys, monkeypatch):
    plan = _plan()
    render = Mock(return_value=plan)
    monkeypatch.setattr("dbt_cortex_agent.eval.verify.build_plan", render)
    payload = _run(_command("eval verify", values), capsys)
    assert render.call_args.kwargs == {"agent_name": "agent", "suite_name": "core", "parse": True}
    assert render.call_args.args[0].project_dir == Path(values["PROJECT_DIR"])
    assert payload["outcome"] == "planned" and payload["applied"] is False
    (suite,) = payload["suites"]
    assert (suite["agent"], suite["suite"], suite["agent_fqn"]) == ("agent", "core", plan.agent_fqn)
    assert suite["eval_model"] == plan.eval_model and suite["baseline_state"] == "not_established"
    assert suite["baseline"] == str(
        Path(values["BASELINE_DIR"]) / "sandbox/DB/AGENTS/AGENT/core.json"
    )
    assert not Path(values["BASELINE_DIR"]).exists()


@pytest.mark.parametrize("command", ["promote", "rollback", "drop"])
def test_skill_lifecycle_previews_use_fresh_manifest(command, values, capsys, monkeypatch):
    manifest = {
        "nodes": {
            "model.consumer.agent": {
                "name": "agent",
                "database": "DB",
                "schema": "RESOLVED_AGENTS",
                "alias": "NAMED_AGENT",
                "config": {"materialized": "cortex_agent"},
            }
        }
    }
    fresh = Mock(return_value=manifest)
    monkeypatch.setattr("dbt_cortex_agent.commands.agent.fresh_manifest", fresh)
    context = Mock(
        return_value=SimpleNamespace(database="DB", role="REVIEWED_ROLE", warehouse="WH")
    )
    monkeypatch.setattr("dbt_cortex_agent.cli.resolve_execution_context", context)
    before = _snapshot(Path(values["PROJECT_DIR"]).parent)
    payload = _run(_command(f"agent {command}", values), capsys)
    assert fresh.call_count == 1 and fresh.call_args.kwargs == {"no_parse": False}
    assert fresh.call_args.args[0].target == "sandbox"
    assert context.call_args.kwargs["role"] == "REVIEWED_ROLE"
    assert payload["agent_fqn"] == "DB.RESOLVED_AGENTS.NAMED_AGENT"
    assert payload["applied"] is False and payload["result"] is None
    if command != "drop":
        assert payload["to_version"] == "VERSION$2" and payload["alias"] == "PRODUCTION"
        assert payload["set_default"] is False
    else:
        assert "stages and skills" in payload["retained"]
    assert _snapshot(Path(values["PROJECT_DIR"]).parent) == before


def test_skill_smoke_requires_explicit_context_and_version_with_optional_tool(values):
    command = _command("agent smoke", values, apply=True)
    args = build_parser().parse_args(command)
    assert args.agent_version == "VERSION$2"
    assert args.role == "REVIEWED_ROLE" and args.connection == "offline"
    assert args.expect_tool == "GovernedAnalytics"
    index = command.index("--expect-tool")
    del command[index : index + 2]
    assert build_parser().parse_args(command).expect_tool is None
    assert "Omit `--expect-tool` only when" in TEXT
    assert "Read version state first" in TEXT
    assert "consumer-role runtime" in TEXT


def test_skill_baseline_preview_first_accept_gate_and_forced_replacement(values, capsys):
    candidate = Path(values["CANDIDATE_JSON"])
    candidate.write_text(json.dumps(_candidate()))
    preview = _command("eval accept-baseline", values)
    apply = _command("eval accept-baseline", values, apply=True)
    root = Path(values["BASELINE_DIR"])
    assert _run(preview, capsys)["baseline"] is None
    assert not root.exists()
    assert "--force requires --apply" in _run([*preview, "--force"], capsys, 2)["error"]
    destination = root / "sandbox/DB/AGENTS/AGENT/core.json"
    suffix = "<target>/<database>/<schema>/<object>/<suite>.json"
    assert f"<BASELINE_DIR>/{suffix}" in TEXT
    for guide in ("docs/reference/cli.md", "docs/guides/evaluations.md"):
        assert f"baselines/{suffix}" in (ROOT / guide).read_text()
    assert _run(apply, capsys)["baseline"] == str(destination)
    assert _run(_command("eval gate", values), capsys)["passed"] is True
    original = destination.read_bytes()
    replacement = {**_candidate(), "run_name": "reviewed_replacement"}
    candidate.write_text(json.dumps(replacement))
    assert "already exists" in _run(apply, capsys, 2)["error"]
    assert destination.read_bytes() == original
    assert _run([*apply, "--force"], capsys)["baseline"] == str(destination)
    assert json.loads(destination.read_text())["run_name"] == "reviewed_replacement"
    assert not Path("target").exists()


@pytest.mark.parametrize(
    "damage", ["failed", "noncompleted", "incomplete", "version_drift", "dataset_drift"]
)
def test_skill_baseline_rejects_invalid_candidates_even_with_force(damage, values, capsys):
    candidate = Path(values["CANDIDATE_JSON"])
    candidate.write_text(json.dumps(_candidate()))
    apply = _command("eval accept-baseline", values, apply=True)
    destination = Path(_run(apply, capsys)["baseline"])
    before = destination.read_bytes()
    invalid = _candidate()
    if damage == "failed":
        invalid["passed"] = False
    elif damage == "noncompleted":
        invalid["status"] = "running"
    elif damage == "incomplete":
        invalid["results"] = []
    elif damage == "version_drift":
        invalid["run_metadata"]["post_completion"]["default_version"] = "VERSION$2"
        invalid["run_metadata"]["default_version_changed"] = True
        invalid.update(status="indeterminate", passed=False)
    else:
        invalid["run_metadata"].update(
            dataset_snapshot=[["Question", "in_scope", "ref"]],
            dataset_source_changed=True,
        )
        invalid["results"][0].update(input="Question", test_type="in_scope")
        invalid.update(status="indeterminate", passed=False)
    candidate.write_text(json.dumps(invalid))
    error = _run([*apply, "--force"], capsys, 2)["error"]
    assert (
        "requires scored row evidence" if damage == "incomplete" else "cannot become baselines"
    ) in error
    assert destination.read_bytes() == before
