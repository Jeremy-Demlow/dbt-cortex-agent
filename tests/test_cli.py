import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import pytest
import yaml

from dbt_cortex_agent import __version__
from dbt_cortex_agent.cli import build_parser, main
from dbt_cortex_agent.commands.common import command_needs_execution_context

ROOT = Path(__file__).parents[1]


def test_parser_exposes_v001_domains_and_no_python_agent_lifecycle():
    parser = build_parser()
    choices = next(action.choices for action in parser._actions if getattr(action, "choices", None))
    assert set(choices) == {"init", "doctor", "manifest", "skill", "agent", "eval"}

    for removed in ("render", "grant"):
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["agent", removed])
        assert exc.value.code == 2

    deploy = parser.parse_args(
        [
            "agent",
            "deploy",
            "--agent",
            "orders_assistant",
            "--target",
            "sandbox",
            "--allow-target",
            "sandbox",
            "--allow-database",
            "DB",
        ]
    )
    assert deploy.apply is False
    parser.parse_args(
        [
            "agent",
            "promote",
            "--agent",
            "orders_assistant",
            "--version",
            "VERSION$2",
            "--alias",
            "production",
        ]
    )
    parser.parse_args(
        [
            "agent",
            "rollback",
            "--agent",
            "orders_assistant",
            "--to-version",
            "VERSION$1",
            "--alias",
            "production",
        ]
    )
    smoke = parser.parse_args(
        [
            "agent",
            "smoke",
            "--agent",
            "orders_assistant",
            "--version",
            "VERSION$2",
            "--question",
            "How many orders?",
        ]
    )
    assert smoke.agent_version == "VERSION$2"


@pytest.mark.parametrize(
    ("argv", "label"),
    [
        (["init", "--help"], "MUTATION"),
        (["skill", "upload", "--help"], "MUTATION"),
        (["skill", "smoke", "--help"], "RUNTIME"),
        (["agent", "smoke", "--help"], "RUNTIME"),
        (["eval", "run", "--help"], "PAID"),
        (["eval", "verify", "--help"], "PAID"),
        (["eval", "accept-baseline", "--help"], "MUTATION"),
    ],
)
def test_help_labels_operation_boundaries(argv, label, capsys):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 0
    assert label in capsys.readouterr().out


def test_agent_smoke_preview_is_structured(monkeypatch, capsys, tmp_path):
    manifest = {
        "nodes": {
            "model.fixture.orders_assistant": {
                "unique_id": "model.fixture.orders_assistant",
                "resource_type": "model",
                "name": "orders_assistant",
                "database": "DB",
                "schema": "AGENTS",
                "alias": "ORDERS_ASSISTANT",
                "config": {"materialized": "cortex_agent"},
            }
        }
    }
    monkeypatch.setattr(
        "dbt_cortex_agent.commands.agent.fresh_manifest", lambda *args, **kwargs: manifest
    )

    assert (
        main(
            [
                "agent",
                "smoke",
                "--project-dir",
                str(tmp_path),
                "--no-parse",
                "--target",
                "sandbox",
                "--agent",
                "orders_assistant",
                "--question",
                "How many orders?",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["agent_object"] == "ORDERS_ASSISTANT"
    assert payload["applied"] is False


def test_eval_run_is_paid_opt_in():
    args = build_parser().parse_args(
        ["eval", "run", "--agent", "orders_assistant", "--suite", "core"]
    )
    assert args.apply is False

    verify = build_parser().parse_args(
        ["eval", "verify", "--agent", "orders_assistant", "--suite", "core"]
    )
    assert verify.apply is False


def test_eval_local_commands_parse_without_connection():
    parser = build_parser()
    parser.parse_args(["eval", "compare", "baseline.json", "candidate.json"])
    parser.parse_args(["eval", "gate", "candidate.json"])
    parser.parse_args(["eval", "accept-baseline", "candidate.json"])


def test_cli_accepts_structured_controlled_failure_from_handler(monkeypatch, tmp_path):
    parser = build_parser()
    args = parser.parse_args(["doctor", "--project-dir", str(tmp_path)])
    args.handler = lambda _args, _config: 2
    monkeypatch.setattr("dbt_cortex_agent.cli.build_parser", lambda: SimpleParser(args))

    assert main([]) == 2


class SimpleParser:
    def __init__(self, args):
        self.args = args

    def parse_args(self, _argv):
        return self.args


def test_explicit_connection_supplies_dbt_environment_for_previews():
    parser = build_parser()

    # Governed profiles build credentials from environment variables, and every
    # manifest-dependent command parses first, so previews need the resolved
    # child environment even though they never mutate or invoke.
    for argv in (
        ["agent", "deploy", "--agent", "a", "--connection", "sandbox"],
        ["eval", "verify", "--agent", "a", "--suite", "core", "--connection", "sandbox"],
        ["manifest", "validate", "--connection", "sandbox"],
        ["doctor", "--connection", "sandbox"],
    ):
        args = parser.parse_args(argv)
        assert command_needs_execution_context(args) is True
        assert getattr(args, "apply", False) is False

    without_connection = parser.parse_args(["agent", "deploy", "--agent", "a"])
    assert command_needs_execution_context(without_connection) is False


def test_v001_identity_is_consistent():
    project = yaml.safe_load((ROOT / "dbt_project.yml").read_text())
    package = tomllib.loads((ROOT / "pyproject.toml").read_text())
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text())
    lock = (ROOT / "uv.lock").read_text()
    readme = (ROOT / "README.md").read_text()
    changelog = (ROOT / "CHANGELOG.md").read_text()

    assert project["version"] == "0.0.6"
    assert package["project"]["version"] == "0.0.6"
    assert citation["version"] == "0.0.6"
    assert __version__ == "0.0.6"
    assert 'name = "dbt-cortex-agent"\nversion = "0.0.6"' in lock
    assert "revision: v0.0.6" in readme
    assert "## 0.0.6 — 2026-08-28" in changelog


def test_runtime_is_the_only_connector_extra():
    package = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert set(package["project"]["optional-dependencies"]) == {"test", "runtime"}
