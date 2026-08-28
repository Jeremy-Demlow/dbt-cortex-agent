from __future__ import annotations

import json
from argparse import Namespace

import pytest
import yaml

# Evidence: TC-024-01 TC-024-03 TC-024-04 TC-024-05 TC-024-06 TC-024-07 TC-024-08
from dbt_cortex_agent.cli import build_parser, main
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.scaffold import apply_scaffold_plan, build_scaffold_plan


def _project(tmp_path):
    (tmp_path / "dbt_project.yml").write_text(
        "name: consumer\nversion: 1.0.0\nconfig-version: 2\n",
        encoding="utf-8",
    )
    return resolve_config(
        Namespace(
            project_dir=str(tmp_path),
            manifest=None,
            target=None,
            connection=None,
            database=None,
            schema=None,
            role=None,
            warehouse=None,
            artifact_dir=None,
            dbt_executable=None,
            snow_executable=None,
        ),
        env={},
    )


def test_bare_scaffold_preview_is_deterministic_and_writes_nothing(tmp_path) -> None:
    config = _project(tmp_path)

    first = build_scaffold_plan(config, "finance_assistant")
    second = build_scaffold_plan(config, "finance_assistant")

    assert first == second
    assert [action.action for action in first.actions] == ["create", "create", "create"]
    assert not (tmp_path / "models").exists()
    sql = dict(first.files)[tmp_path / "models/agents/finance_assistant/finance_assistant.sql"]
    assert "semantic_view" not in sql
    assert "experimental:" not in sql
    assert "What questions can you help me answer?" in sql


def test_scaffold_apply_is_idempotent_and_fails_closed_on_collision(tmp_path) -> None:
    config = _project(tmp_path)
    plan = build_scaffold_plan(config, "finance_assistant", with_eval=True)

    changed = apply_scaffold_plan(plan)
    repeated = build_scaffold_plan(config, "finance_assistant", with_eval=True)

    assert len(changed) == 5
    assert repeated.files == ()
    assert all(action.action == "unchanged" for action in repeated.actions)
    collision = tmp_path / "models/agents/finance_assistant/agent.yml"
    collision.write_text("different\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="existing content differs"):
        build_scaffold_plan(config, "finance_assistant", with_eval=True)


def test_optional_semantic_view_generates_analyst_dependency(tmp_path) -> None:
    config = _project(tmp_path)
    plan = build_scaffold_plan(config, "finance_assistant", "sem_finance")
    sql = dict(plan.files)[tmp_path / "models/agents/finance_assistant/finance_assistant.sql"]

    assert "ref('sem_finance')" in sql
    assert "cortex_agent__semantic_view_fqn('sem_finance')" in sql
    assert "cortex_analyst_text_to_sql" in sql
    assert 'semantic_view: "{{ semantic_view_fqn }}"' in sql


def test_scaffold_has_no_private_preview_options() -> None:
    args = build_parser().parse_args(["agent", "scaffold", "--agent", "a"])

    assert not hasattr(args, "enable_cortex_sense")
    assert not hasattr(args, "fallback_warehouse")


def test_experimental_mapping_is_valid_full_body_yaml(tmp_path) -> None:
    config = _project(tmp_path)
    plan = build_scaffold_plan(config, "finance_assistant")
    sql = dict(plan.files)[tmp_path / "models/agents/finance_assistant/finance_assistant.sql"]
    body = sql.split("models:\n", 1)[1]
    spec = yaml.safe_load(
        "models:\n"
        + body.replace(
            "  sample_questions:\n    - question: What questions can you help me answer?\n",
            "  sample_questions:\n    - question: What questions can you help me answer?\n"
            "\nexperimental:\n  EnableCortexSense: true\n  FallbackWarehouse: COMPUTE_WH\n",
        )
    )

    assert spec["experimental"] == {
        "EnableCortexSense": True,
        "FallbackWarehouse": "COMPUTE_WH",
    }


def test_scaffold_cli_preview_and_apply_emit_stable_json(tmp_path, capsys) -> None:
    _project(tmp_path)
    argv = [
        "agent",
        "scaffold",
        "--project-dir",
        str(tmp_path),
        "--agent",
        "finance_assistant",
        "--json",
    ]

    assert main(argv) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["applied"] is False
    assert [item["action"] for item in preview["actions"]] == ["create", "create", "create"]

    assert main([*argv[:-1], "--apply", "--json"]) == 0
    applied = json.loads(capsys.readouterr().out)
    assert applied["applied"] is True
    assert (tmp_path / "models/agents/finance_assistant/finance_assistant.sql").is_file()


@pytest.mark.parametrize("name", ["Finance", "finance-agent", "1agent", "agent/path", ""])
def test_scaffold_rejects_unsafe_logical_names(tmp_path, name) -> None:
    with pytest.raises(ValueError, match="lowercase"):
        build_scaffold_plan(_project(tmp_path), name)
