import json

import pytest

from dbt_cortex_agent.cli import build_parser
from dbt_cortex_agent.commands.agent import _handle_smoke
from dbt_cortex_agent.config import Config


@pytest.mark.parametrize("domain", ["agent", "skill"])
@pytest.mark.parametrize("invalid", ["0", "-1", "nan", "inf", "-inf", "1e999", "bad"])
def test_cli_rejects_invalid_runtime_budget(domain, invalid):
    command = [domain, "smoke", "--agent", "demo"]
    if domain == "agent":
        command += ["--question", "question"]
    with pytest.raises(SystemExit) as caught:
        build_parser().parse_args([*command, f"--timeout-seconds={invalid}"])
    assert caught.value.code == 2


@pytest.mark.parametrize("domain", ["agent", "skill"])
def test_cli_default_and_fractional_budget(domain):
    command = [domain, "smoke", "--agent", "demo"]
    if domain == "agent":
        command += ["--question", "question"]
    assert build_parser().parse_args(command).timeout_seconds == 60
    assert (
        build_parser().parse_args([*command, "--timeout-seconds", "120.5"]).timeout_seconds == 120.5
    )


def test_agent_preview_and_apply_forward_budget(tmp_path, monkeypatch, capsys):
    config = Config(
        project_dir=tmp_path,
        manifest=tmp_path / "target/manifest.json",
        target="sandbox",
        connection="conn",
        connection_explicit=True,
        database="DB",
        database_explicit=True,
        schema="S",
        role="ROLE",
        warehouse="WH",
        warehouse_explicit=True,
        artifact_dir=tmp_path / "target/dbt_cortex_agent",
        dbt_executable="dbt",
        snow_executable="snow",
    )
    manifest = {
        "nodes": {
            "model.demo.agent": {
                "name": "demo",
                "unique_id": "model.demo.agent",
                "resource_type": "model",
                "database": "DB",
                "schema": "S",
                "alias": "DEMO",
                "config": {"materialized": "cortex_agent"},
            }
        }
    }
    args = build_parser().parse_args(
        [
            "agent",
            "smoke",
            "--agent",
            "demo",
            "--question",
            "question",
            "--timeout-seconds",
            "120.5",
            "--allow-target",
            "sandbox",
            "--allow-database",
            "DB",
            "--json",
        ]
    )
    calls = []

    def invoke(*args, **kwargs):
        calls.append(kwargs)
        return {"answer": "done", "tool_uses": []}

    monkeypatch.setattr("dbt_cortex_agent.commands.agent.invoke_agent", invoke)
    assert _handle_smoke(args, config, manifest) == 0
    assert not calls
    assert json.loads(capsys.readouterr().out)["timeout_seconds"] == 120.5
    args.apply = True
    assert _handle_smoke(args, config, manifest) == 0
    assert calls[0]["timeout"] == 120.5
