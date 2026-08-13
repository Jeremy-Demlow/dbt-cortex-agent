from __future__ import annotations

from pathlib import Path
import json
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from urllib.error import HTTPError, URLError

import pytest
import yaml

from dbt_cortex_agent import __version__
from dbt_cortex_agent.cli import build_parser, main
from dbt_cortex_agent.init import DEFAULT_REVISION


def test_agent_grant_dispatch_does_not_require_promote_or_rollback_args(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "dbt_project.yml").write_text("name: fixture\nversion: 1.0.0\nconfig-version: 2\n")
    manifest = project / "target" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
                "nodes": {},
                "exposures": {
                    "exposure.fixture.agent": {
                        "name": "agent",
                        "config": {"meta": {"cortex_agent": {"enabled": True}}},
                    }
                },
            }
        )
    )

    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.fresh_manifest",
        lambda *_args, **_kwargs: json.loads(manifest.read_text()),
    )
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.lifecycle_macro",
        lambda *_args, **_kwargs: type("Result", (), {"agents": ("agent",)})(),
    )

    assert (
        main(
            [
                "agent",
                "grant",
                "--project-dir",
                str(project),
                "--manifest",
                str(manifest),
                "--agent",
                "agent",
            ]
        )
        == 0
    )


def test_parser_exposes_foundation_and_lifecycle_commands():
    parser = build_parser()
    choices = next(
        action.choices for action in parser._actions if getattr(action, "choices", None)
    )

    assert set(choices) == {"init", "doctor", "manifest", "skill", "agent", "eval"}


def test_shared_options_parse_for_both_commands():
    parser = build_parser()
    values = [
        "--project-dir", "/tmp/project", "--manifest", "build/manifest.json",
        "--target", "sandbox", "--connection", "test", "--database", "DB",
        "--schema", "AGENTS", "--warehouse", "WH",
        "--artifact-dir", "artifacts",
    ]

    for command in ("init", "doctor"):
        args = parser.parse_args([command, *values])
        assert args.project_dir == "/tmp/project"
        assert args.manifest == "build/manifest.json"
        assert args.connection == "test"


def test_init_exposes_explicit_bootstrap_options():
    args = build_parser().parse_args(
        [
            "init",
            "--package-source", "https://example.invalid/repo.git",
            "--revision", "v9",
            "--target", "safe",
            "--allow-target", "qa",
            "--allow-target", "prod",
            "--allow-database", "DB",
            "--allow-database", "AUDIT",
            "--agent-schema", "AGENTS",
            "--eval-schema", "EVAL",
            "--starter", "orders",
        ]
    )

    assert args.package_source == "https://example.invalid/repo.git"
    assert args.revision == "v9"
    assert args.allow_target == ["qa", "prod"]
    assert args.allow_database == ["DB", "AUDIT"]
    assert args.agent_schema == "AGENTS"
    assert args.eval_schema == "EVAL"
    assert args.starter == "orders"


def test_orders_starter_json_preview_is_structured(tmp_path, capsys):
    (tmp_path / "dbt_project.yml").write_text(
        "name: consumer\nversion: 1.0.0\nconfig-version: 2\n"
    )

    assert main([
        "init", "--project-dir", str(tmp_path), "--starter", "orders",
        "--package-source", "https://example.invalid/repo.git", "--json",
    ]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "init"
    assert payload["starter"] == "orders"
    assert payload["applied"] is False
    assert payload["changed_files"] == []
    assert {Path(item["path"]).relative_to(tmp_path).as_posix() for item in payload["actions"]} == {
        "packages.yml",
        "models/semantic/sem_orders.sql",
        "models/agents/orders_assistant/agent.yml",
        "models/agents/orders_assistant/orders_assistant.sql",
        "models/agents/orders_assistant/evals/orders_assistant_core.sql",
        "models/agents/orders_assistant/evals/core.yml",
        "seeds/orders.csv",
        "seeds/orders.yml",
        ".dbtignore",
    }
    assert not (tmp_path / "models").exists()


def test_orders_starter_json_apply_reports_written_paths(tmp_path, capsys):
    (tmp_path / "dbt_project.yml").write_text(
        "name: consumer\nversion: 1.0.0\nconfig-version: 2\n"
    )

    assert main([
        "init", "--project-dir", str(tmp_path), "--starter", "orders",
        "--package-source", "https://example.invalid/repo.git", "--apply", "--json",
    ]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["applied"] is True
    assert {Path(path).relative_to(tmp_path).as_posix() for path in payload["changed_files"]} == {
        item["path"].removeprefix(f"{tmp_path}/")
        for item in payload["actions"]
        if item["action"] != "unchanged"
    }
    assert all(Path(path).is_file() for path in payload["changed_files"])


def test_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "{init,doctor,manifest,skill,agent,eval}" in output
    assert "Mutation and paid commands are dry-run by default" in output
    assert "Examples:" in output


@pytest.mark.parametrize(
    ("argv", "label"),
    [
        (["init", "--help"], "MUTATION"),
        (["skill", "upload", "--help"], "MUTATION"),
        (["skill", "smoke", "--help"], "RUNTIME"),
        (["agent", "smoke", "--help"], "RUNTIME"),
        (["agent", "deploy", "--help"], "MUTATION"),
        (["eval", "run", "--help"], "PAID"),
        (["eval", "accept-baseline", "--help"], "MUTATION"),
        (["eval", "migrate-baseline", "--help"], "MUTATION"),
    ],
)
def test_help_labels_apply_boundaries(argv, label, capsys):
    with pytest.raises(SystemExit) as exc:
        main(argv)

    assert exc.value.code == 0
    assert label in capsys.readouterr().out


def test_eval_run_is_paid_opt_in():
    args = build_parser().parse_args(
        ["eval", "run", "--agent", "orders_assistant", "--suite", "core"]
    )

    assert args.apply is False


def test_agent_lifecycle_commands_do_not_expose_projection():
    parser = build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["agent", "deploy", "--projection", "native_eval"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        parser.parse_args([
            "agent", "smoke", "--agent", "a", "--question", "q",
            "--projection", "canonical",
        ])
    assert exc.value.code == 2


def test_agent_smoke_requires_agent_and_question():
    parser = build_parser()

    with pytest.raises(SystemExit) as missing_agent:
        parser.parse_args(["agent", "smoke", "--question", "hello"])
    with pytest.raises(SystemExit) as missing_question:
        parser.parse_args(["agent", "smoke", "--agent", "orders_assistant"])

    assert missing_agent.value.code == 2
    assert missing_question.value.code == 2


def test_agent_smoke_preview_is_structured_and_does_not_invoke(
    monkeypatch, capsys, tmp_path
):
    manifest = {
        "exposures": {
            "exposure.fixture.orders_assistant": {
                "name": "orders_assistant",
                "meta": {
                    "cortex_agent": {
                        "enabled": True,
                        "naming": {"sandbox": "ORDERS_SANDBOX"},
                    }
                },
            }
        }
    }
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.fresh_manifest", lambda *args, **kwargs: manifest
    )
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.invoke_agent",
        lambda *args, **kwargs: pytest.fail("Agent invoked during preview"),
    )

    assert main([
        "agent", "smoke", "--project-dir", str(tmp_path), "--no-parse",
        "--target", "sandbox", "--agent", "orders_assistant",
        "--question", " How many orders? ", "--expect-tool", " analyst ",
        "--agent-object", "ORDERS_OVERRIDE", "--endpoint",
        "https://example.snowflakecomputing.com", "--json",
    ]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "command": "agent smoke",
        "applied": False,
        "agent": "orders_assistant",
        "agent_object": "ORDERS_OVERRIDE",
        "question": " How many orders? ",
        "expected_tool": " analyst ",
        "passed": None,
        "response": None,
    }


@pytest.mark.parametrize(("option", "value"), [("--agent", "   "), ("--question", "\t")])
def test_agent_smoke_rejects_blank_required_values(monkeypatch, tmp_path, option, value):
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.fresh_manifest", lambda *args, **kwargs: {}
    )
    argv = [
        "agent", "smoke", "--project-dir", str(tmp_path), "--no-parse",
        "--agent", "orders_assistant", "--question", "question",
    ]
    argv[argv.index(option) + 1] = value

    assert main(argv) == 2


def test_agent_smoke_apply_reuses_invoker_and_exact_tool_assertion(
    monkeypatch, capsys, tmp_path
):
    manifest = {
        "metadata": {"project_name": "fixture"},
        "nodes": {
            "model.fixture.orders": {
                "name": "orders",
                "database": "DB",
                "schema": "DATA",
                "resource_type": "model",
                "package_name": "fixture",
            }
        },
        "exposures": {
            "exposure.fixture.orders_assistant": {
                "name": "orders_assistant",
                "meta": {
                    "cortex_agent": {
                        "enabled": True,
                        "naming": {"sandbox": "ORDERS_SANDBOX"},
                    }
                },
            }
        },
    }
    calls = []
    response = {
        "answer": "42",
        "tool_uses": [{"name": "analyst", "input": {}}],
        "tool_results": [],
    }
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.fresh_manifest", lambda *args, **kwargs: manifest
    )
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.invoke_agent",
        lambda *args: calls.append(args) or response,
    )
    monkeypatch.setattr(
        "dbt_cortex_agent.cli.resolve_execution_context",
        lambda **kwargs: type(
            "Context",
            (),
            {"database": "DB", "warehouse": None, "dbt_env": {}},
        )(),
    )

    argv = [
        "agent", "smoke", "--project-dir", str(tmp_path), "--no-parse",
        "--target", "sandbox", "--connection", "conn", "--database", "DB",
        "--schema", "AGENTS", "--allow-target", "sandbox",
        "--allow-database", "DB", "--agent", "orders_assistant",
        "--question", "How many orders?", "--expect-tool", "analyst",
        "--endpoint", "https://example.snowflakecomputing.com", "--apply", "--json",
    ]
    assert main(argv) == 0

    assert calls == [(
        "DB", "AGENTS", "ORDERS_SANDBOX", "How many orders?", "conn",
        "https://example.snowflakecomputing.com",
    )]
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert payload["response"] == response

    argv[argv.index("analyst")] = "Analyst"
    assert main(argv) == 2
    assert "expected tool 'Analyst' was not selected" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        ["--target", "sandbox", "--database", "DB", "--schema", "AGENTS"],
        ["--target", "sandbox", "--connection", "conn", "--schema", "AGENTS"],
        [
            "--target", "sandbox", "--connection", "conn", "--database", "OTHER",
            "--schema", "AGENTS", "--allow-target", "sandbox", "--allow-database", "OTHER",
        ],
        [
            "--target", "sandbox", "--connection", "conn", "--database", "DB",
            "--schema", "AGENTS", "--allow-database", "DB",
        ],
        [
            "--target", "sandbox", "--connection", "conn", "--database", "DB",
            "--schema", "AGENTS", "--allow-target", "sandbox",
        ],
        [
            "--target", "sandbox", "--connection", "conn", "--database", "DB",
            "--allow-target", "sandbox", "--allow-database", "DB",
        ],
    ],
)
def test_agent_smoke_apply_gates_before_invocation(monkeypatch, tmp_path, args):
    manifest = {
        "metadata": {"project_name": "fixture"},
        "nodes": {
            "model.fixture.orders": {
                "name": "orders",
                "database": "DB",
                "schema": "DATA",
                "resource_type": "model",
                "package_name": "fixture",
            }
        },
        "exposures": {
            "exposure.fixture.orders_assistant": {
                "name": "orders_assistant",
                "meta": {
                    "cortex_agent": {
                        "enabled": True,
                        "naming": {"sandbox": "ORDERS_SANDBOX"},
                    }
                },
            }
        }
    }
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.fresh_manifest", lambda *args, **kwargs: manifest
    )
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.invoke_agent",
        lambda *args: pytest.fail("Agent invoked before safety gates completed"),
    )

    assert main([
        "agent", "smoke", "--project-dir", str(tmp_path), "--no-parse",
        *args, "--agent", "orders_assistant", "--question", "question", "--apply",
    ]) == 2


def test_agent_smoke_rejects_unsafe_physical_override(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.fresh_manifest",
        lambda *args, **kwargs: {
            "exposures": {
                "exposure.fixture.orders_assistant": {
                    "name": "orders_assistant",
                    "meta": {"cortex_agent": {"enabled": True}},
                }
            }
        },
    )

    assert main([
        "agent", "smoke", "--project-dir", str(tmp_path), "--no-parse",
        "--agent", "orders_assistant", "--agent-object", "BAD;DROP",
        "--question", "question",
    ]) == 2


def test_agent_deploy_human_output_does_not_require_render_artifact(
    monkeypatch, capsys, tmp_path
):
    result = type(
        "Result",
        (),
        {
            "agents": ("agent",),
            "renders": (
                {
                    "agent": "agent",
                    "physical_agent": "DB.AGENTS.AGENT",
                    "lifecycle_contract": "single_agent",
                    "spec": {"tools": []},
                    "target": "sandbox",
                },
            ),
        },
    )()
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.fresh_manifest", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.deploy_agents", lambda *args, **kwargs: result
    )

    assert main([
        "agent", "deploy", "--project-dir", str(tmp_path), "--no-parse",
        "--agent", "agent",
    ]) == 0
    output = capsys.readouterr().out
    assert "DB.AGENTS.AGENT" in output
    assert "Artifact:" not in output


def test_eval_run_exposes_shared_allowlists():
    args = build_parser().parse_args(
        [
            "eval", "run", "--agent", "orders_assistant", "--suite", "core",
            "--allow-target", "sandbox", "--allow-database", "DB",
        ]
    )

    assert args.allow_target == ["sandbox"]
    assert args.allow_database == ["DB"]


def test_all_apply_commands_are_opt_in():
    parser = build_parser()
    commands = [
        ["init"],
        ["skill", "upload"],
        ["skill", "smoke"],
        ["agent", "smoke", "--agent", "a", "--question", "q"],
        ["agent", "deploy"],
        ["agent", "grant"],
        ["agent", "promote", "--from-alias", "A", "--to-alias", "B"],
        ["agent", "rollback", "--alias", "A", "--to-version", "VERSION$1"],
        ["eval", "run", "--agent", "a", "--suite", "s"],
        ["eval", "accept-baseline", "candidate.json"],
        [
            "eval", "migrate-baseline", "legacy.json", "--agent", "a",
            "--suite", "s", "--baseline-dir", "baselines",
        ],
    ]

    assert all(parser.parse_args(command).apply is False for command in commands)


def test_eval_local_commands_parse_without_connection():
    parser = build_parser()

    assert parser.parse_args(["eval", "compare", "base.json", "candidate.json"]).connection is None
    assert parser.parse_args(["eval", "accept-baseline", "candidate.json"]).connection is None
    assert parser.parse_args(["eval", "gate", "candidate.json"]).connection is None


def test_eval_plan_error_is_controlled(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.eval.build_plan",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("invalid dbt eval plan")),
    )
    assert main([
        "eval", "run", "--project-dir", str(tmp_path), "--no-parse",
        "--agent", "orders_assistant", "--suite", "core",
    ]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "error: invalid dbt eval plan"


def test_manifest_commands_parse_by_default_and_no_parse_is_explicit(monkeypatch, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "manifest.json").write_text(
        '{"metadata":{"dbt_schema_version":"https://schemas.getdbt.com/dbt/manifest/v12.json"},"exposures":{}}'
    )
    calls = []

    def fake_parse(executable, project_dir, target_name, runner, env=None):
        calls.append((executable, project_dir, target_name))
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("dbt_cortex_agent.commands.common.run_dbt_parse", fake_parse)
    assert main(["manifest", "validate", "--project-dir", str(tmp_path)]) == 0
    assert len(calls) == 1
    assert main(["manifest", "validate", "--project-dir", str(tmp_path), "--no-parse"]) == 0
    assert len(calls) == 1


def test_parse_failure_prevents_manifest_load(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.common.run_dbt_parse",
        lambda *args, **kwargs: type(
            "Result", (), {"returncode": 1, "stdout": "", "stderr": "parse failed"}
        )(),
    )
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.common.load_manifest",
        lambda *args: pytest.fail("manifest loaded after parse failure"),
    )

    assert main(["manifest", "validate", "--project-dir", str(tmp_path)]) == 2


def test_mutating_cli_requires_explicit_connection_not_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("SNOWFLAKE_CONNECTION_NAME", "environment-only")
    target = tmp_path / "target"
    target.mkdir()
    (target / "manifest.json").write_text(
        '{"metadata":{"dbt_schema_version":"https://schemas.getdbt.com/dbt/manifest/v12.json"},'
        '"exposures":{"exposure.x":{"name":"x","meta":{"cortex_agent":{"enabled":true}}}},'
        '"nodes":{"model.x":{"name":"x","database":"DB","schema":"S","resource_type":"model"}}}'
    )

    assert main([
        "agent", "grant", "--project-dir", str(tmp_path), "--no-parse", "--agent", "x",
        "--database", "DB", "--target", "sandbox", "--allow-target", "sandbox",
        "--allow-database", "DB", "--apply",
    ]) == 2


def test_skill_smoke_override_requires_exactly_one_agent(monkeypatch, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "manifest.json").write_text(
        '{"metadata":{"dbt_schema_version":"https://schemas.getdbt.com/dbt/manifest/v12.json"},'
        '"exposures":{'
        '"exposure.a":{"name":"a","meta":{"cortex_agent":{"enabled":true,"naming":{"sandbox":"A"}}}},'
        '"exposure.b":{"name":"b","meta":{"cortex_agent":{"enabled":true,"naming":{"sandbox":"B"}}}}}}'
    )

    assert main([
        "skill", "smoke", "--project-dir", str(tmp_path), "--no-parse",
        "--target", "sandbox", "--agent-object", "OVERRIDE",
    ]) == 2


def test_skill_smoke_rejects_unsafe_single_agent_override(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "manifest.json").write_text(
        '{"metadata":{"dbt_schema_version":"https://schemas.getdbt.com/dbt/manifest/v12.json"},'
        '"exposures":{"exposure.a":{"name":"a","meta":{"cortex_agent":{"enabled":true}}}}}'
    )

    assert main([
        "skill", "smoke", "--project-dir", str(tmp_path), "--no-parse",
        "--agent", "a", "--agent-object", "BAD;DROP",
    ]) == 2


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == __version__


def test_manifest_json_output_is_machine_readable(tmp_path, capsys):
    target = tmp_path / "target"
    target.mkdir()
    (target / "manifest.json").write_text(
        '{"metadata":{"dbt_schema_version":"https://schemas.getdbt.com/dbt/manifest/v12.json"},'
        '"exposures":{"exposure.a":{"name":"a","meta":{"cortex_agent":{"enabled":true}}}}}'
    )

    assert main(["manifest", "validate", "--project-dir", str(tmp_path), "--no-parse", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "manifest": str(target / "manifest.json"),
        "agents": ["a"],
    }


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("missing file"),
        PermissionError("permission denied"),
        json.JSONDecodeError("bad json", "{", 1),
        HTTPError("https://example.invalid", 500, "server error", {}, None),
        URLError("connection failed"),
    ],
)
def test_expected_runtime_errors_are_controlled(monkeypatch, capsys, error):
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.eval.gate_candidate",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )

    assert main(["eval", "gate", "candidate.json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "Traceback" not in captured.err


def test_json_error_is_machine_readable(monkeypatch, capsys):
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.eval.gate_candidate",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("invalid candidate")),
    )

    assert main(["eval", "gate", "candidate.json", "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {"error": "invalid candidate", "exit_code": 2}


def test_baseline_accept_is_preview_by_default(monkeypatch, tmp_path, capsys):
    candidate = {"agent": "a", "suite": "s"}
    monkeypatch.setattr("dbt_cortex_agent.commands.eval.load_result", lambda *args: candidate)
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.eval.accept_baseline",
        lambda *args, **kwargs: pytest.fail("baseline written during preview"),
    )

    assert main(["eval", "accept-baseline", "candidate.json", "--baseline-dir", str(tmp_path)]) == 0
    assert "[DRY RUN] would accept baseline" in capsys.readouterr().out


def test_legacy_baseline_migration_is_preview_by_default(monkeypatch, tmp_path, capsys):
    plan = type("Plan", (), {})()
    monkeypatch.setattr("dbt_cortex_agent.commands.eval.build_plan", lambda *args, **kwargs: plan)
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.eval.migrate_legacy_baseline",
        lambda *args, **kwargs: (
            {"agent": "a", "suite": "s"},
            tmp_path / "baselines" / "a" / "s.json",
        ),
    )

    assert main([
        "eval", "migrate-baseline", "legacy.json", "--project-dir", str(tmp_path),
        "--no-parse", "--agent", "a", "--suite", "s",
        "--baseline-dir", str(tmp_path / "baselines"),
    ]) == 0
    assert "[DRY RUN] would migrate legacy baseline" in capsys.readouterr().out


def test_package_root_public_api_is_version_only():
    import dbt_cortex_agent

    assert dbt_cortex_agent.__all__ == ["__version__"]


def test_runtime_is_the_only_connector_extra():
    root = Path(__file__).parents[1]
    package = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    extras = package["project"]["optional-dependencies"]

    assert set(extras) == {"test", "runtime"}
    assert extras["runtime"] == ["snowflake-connector-python>=3.18,<5"]


def test_cli_module_is_thin_domain_dispatcher():
    root = Path(__file__).parents[1]
    cli = (root / "src/dbt_cortex_agent/cli.py").read_text(encoding="utf-8")

    assert "args.handler(args, config)" in cli
    assert "if args.command" not in cli
    for module in ("bootstrap", "manifest", "skill", "agent", "eval"):
        assert (root / f"src/dbt_cortex_agent/commands/{module}.py").is_file()


def test_v031_identity_is_consistent_and_release_history_is_preserved():
    root = Path(__file__).parents[1]
    project = yaml.safe_load((root / "dbt_project.yml").read_text(encoding="utf-8"))
    citation = yaml.safe_load((root / "CITATION.cff").read_text(encoding="utf-8"))
    package = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    lock = (root / "uv.lock").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    installation = (root / "docs/getting-started/installation.md").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    assert project["version"] == "0.3.1"
    assert package["project"]["version"] == "0.3.1"
    assert citation["version"] == "0.3.1"
    assert __version__ == "0.3.1"
    assert DEFAULT_REVISION == f"v{__version__}"
    assert 'name = "dbt-cortex-agent"\nversion = "0.3.1"' in lock
    assert "public HTTPS `v0.3.1` Git tag" in readme
    assert "revision: v0.3.1" in installation
    assert "## 0.3.1 — 2026-08-07" in changelog
    assert "## 0.3.0 — 2026-08-06" in changelog
    assert "## 0.2.0 — 2026-07-31" in changelog