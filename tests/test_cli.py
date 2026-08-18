from pathlib import Path
import json
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import pytest
import yaml

from dbt_cortex_agent import __version__
from dbt_cortex_agent.cli import build_parser, main


ROOT = Path(__file__).parents[1]


def test_parser_exposes_v001_domains_and_no_python_agent_lifecycle():
    parser = build_parser()
    choices = next(
        action.choices for action in parser._actions if getattr(action, "choices", None)
    )
    assert set(choices) == {"init", "doctor", "manifest", "skill", "agent", "eval"}

    for removed in ("render", "deploy", "grant", "promote", "rollback"):
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["agent", removed])
        assert exc.value.code == 2


@pytest.mark.parametrize(
    ("argv", "label"),
    [
        (["init", "--help"], "MUTATION"),
        (["skill", "upload", "--help"], "MUTATION"),
        (["skill", "smoke", "--help"], "RUNTIME"),
        (["agent", "smoke", "--help"], "RUNTIME"),
        (["eval", "run", "--help"], "PAID"),
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

    assert main([
        "agent", "smoke", "--project-dir", str(tmp_path), "--no-parse",
        "--target", "sandbox", "--agent", "orders_assistant",
        "--question", "How many orders?", "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["agent_object"] == "ORDERS_ASSISTANT"
    assert payload["applied"] is False


def test_eval_run_is_paid_opt_in():
    args = build_parser().parse_args(
        ["eval", "run", "--agent", "orders_assistant", "--suite", "core"]
    )
    assert args.apply is False


def test_eval_local_commands_parse_without_connection():
    parser = build_parser()
    parser.parse_args(["eval", "compare", "baseline.json", "candidate.json"])
    parser.parse_args(["eval", "gate", "candidate.json"])
    parser.parse_args(["eval", "accept-baseline", "candidate.json"])


def test_v001_identity_is_consistent():
    project = yaml.safe_load((ROOT / "dbt_project.yml").read_text())
    package = tomllib.loads((ROOT / "pyproject.toml").read_text())
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text())
    lock = (ROOT / "uv.lock").read_text()
    readme = (ROOT / "README.md").read_text()
    changelog = (ROOT / "CHANGELOG.md").read_text()

    assert project["version"] == "0.0.1"
    assert package["project"]["version"] == "0.0.1"
    assert citation["version"] == "0.0.1"
    assert __version__ == "0.0.1"
    assert 'name = "dbt-cortex-agent"\nversion = "0.0.1"' in lock
    assert "revision: v0.0.1" in readme
    assert "## 0.0.1 — 2026-08-18" in changelog


def test_runtime_is_the_only_connector_extra():
    package = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert set(package["project"]["optional-dependencies"]) == {"test", "runtime"}