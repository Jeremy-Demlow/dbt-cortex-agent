from __future__ import annotations

import json

import pytest

from dbt_cortex_agent.manifest import (
    assert_config_database, cortex_agents, cortex_evals, load_manifest, physical_agent_name,
    select_agents, skill_declarations, validate_manifest,
)


def _manifest():
    return {
        "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
        "exposures": {
            "exposure.consumer.agent": {
                "name": "orders_assistant",
                "config": {"meta": {"cortex_agent": {
                    "enabled": True,
                    "capabilities": {"skills": [{
                        "name": "triage", "source": {"type": "stage", "path": "@DB.AGENTS.SKILLS/agents/orders_assistant/triage"}
                    }]},
                }}},
            },
            "exposure.consumer.disabled": {
                "name": "disabled", "meta": {"cortex_agent": {"enabled": False}}
            },
        },
        "nodes": {
            "model.consumer.eval_orders": {
                "unique_id": "model.consumer.eval_orders", "name": "eval_orders",
                "database": "db", "schema": "eval", "alias": "eval_orders_table",
                "config": {"meta": {"cortex_eval": {"enabled": True}}},
            }
        },
    }


def test_load_manifest_v12_and_enumerate_metadata(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_manifest()))

    manifest = load_manifest(path)

    assert [item["name"] for item in cortex_agents(manifest)] == ["orders_assistant"]
    assert cortex_evals(manifest)[0].table_fqn == "DB.EVAL.EVAL_ORDERS_TABLE"
    skill = skill_declarations(manifest, tmp_path)[0]
    assert skill.local_dir == tmp_path / "models/agents/orders_assistant/skills/triage"


@pytest.mark.parametrize("manifest", [{}, {"metadata": {}}, {"metadata": {"dbt_schema_version": "v11.json"}}])
def test_manifest_validation_fails_closed(manifest):
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_load_manifest_rejects_malformed_json(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("{")

    with pytest.raises(ValueError, match="Invalid JSON"):
        load_manifest(path)


def test_load_manifest_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="dbt parse"):
        load_manifest(tmp_path / "manifest.json")


def test_selected_agents_are_exact_and_fail_closed():
    manifest = _manifest()

    assert [item["name"] for item in select_agents(manifest, ["orders_assistant"])] == [
        "orders_assistant"
    ]
    with pytest.raises(ValueError, match="Unknown enabled cortex_agent"):
        select_agents(manifest, ["orders"])


def test_eval_discovery_requires_nonempty_enabled_mapping():
    manifest = _manifest()
    manifest["nodes"].update(
        {
            "model.consumer.absent": {"name": "absent", "database": "DB", "schema": "EVAL"},
            "model.consumer.empty": {
                "name": "empty", "database": "DB", "schema": "EVAL",
                "meta": {"cortex_eval": {}},
            },
            "model.consumer.disabled": {
                "name": "disabled", "database": "DB", "schema": "EVAL",
                "meta": {"cortex_eval": {"enabled": False}},
            },
            "model.consumer.invalid": {
                "name": "invalid", "database": "DB", "schema": "EVAL",
                "meta": {"cortex_eval": "yes"},
            },
        }
    )

    assert [item.model_name for item in cortex_evals(manifest)] == ["eval_orders"]


def test_manifest_database_and_physical_agent_validation():
    manifest = _manifest()
    manifest["nodes"]["model.consumer.eval_orders"]["resource_type"] = "model"
    manifest["exposures"]["exposure.consumer.agent"]["config"]["meta"]["cortex_agent"].update(
        {"snowflake_name": "ORDERS", "naming": {"sandbox": "ORDERS_SANDBOX"}}
    )

    assert assert_config_database(manifest, "db") == "DB"
    assert physical_agent_name(select_agents(manifest)[0], "sandbox") == "ORDERS_SANDBOX"
    with pytest.raises(ValueError, match="does not match"):
        assert_config_database(manifest, "OTHER")
    with pytest.raises(ValueError, match="unquoted"):
        manifest["exposures"]["exposure.consumer.agent"]["config"]["meta"]["cortex_agent"]["snowflake_name"] = "BAD;DROP"
        physical_agent_name(select_agents(manifest)[0], None)

    manifest["exposures"]["exposure.consumer.agent"]["config"]["meta"]["cortex_agent"]["naming"] = {}
    with pytest.raises(ValueError, match="does not guess"):
        physical_agent_name(select_agents(manifest)[0], "sandbox")