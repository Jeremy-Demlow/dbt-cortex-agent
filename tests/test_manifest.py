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
        "exposures": {},
        "nodes": {
            "model.consumer.orders_assistant": {
                "unique_id": "model.consumer.orders_assistant",
                "resource_type": "model",
                "name": "orders_assistant",
                "alias": "ORDERS_ASSISTANT",
                "database": "db",
                "schema": "agents",
                "config": {"materialized": "cortex_agent", "meta": {"cortex_agent": {
                    "skills": [{"name": "triage", "source": {"type": "stage", "path": "@DB.AGENTS.SKILLS/agents/orders_assistant/triage"}}]
                }}},
            },
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


def test_cortex_agent_models_are_primary_manifest_declarations():
    manifest = _manifest()
    manifest["exposures"] = {}
    manifest["nodes"]["model.consumer.orders_assistant"] = {
        "unique_id": "model.consumer.orders_assistant",
        "resource_type": "model",
        "name": "orders_assistant",
        "alias": "ORDERS_ASSISTANT_DBT_FOCUS",
        "database": "db",
        "schema": "agents",
        "config": {
            "materialized": "cortex_agent",
            "meta": {
                "cortex_agent": {
                    "skills": [
                        {
                            "name": "triage",
                            "source": {
                                "type": "stage",
                                "path": "@DB.AGENTS.SKILLS/agents/orders_assistant/triage",
                            },
                        }
                    ]
                }
            },
        },
    }

    agent = select_agents(manifest)[0]

    assert agent["resource_type"] == "model"
    assert agent["physical_fqn"] == "DB.AGENTS.ORDERS_ASSISTANT_DBT_FOCUS"
    assert physical_agent_name(agent, "dbt_focus") == "ORDERS_ASSISTANT_DBT_FOCUS"
    assert skill_declarations(manifest, ".")[0].agent_name == "orders_assistant"


def test_duplicate_model_logical_agent_fails_closed():
    manifest = _manifest()
    manifest["nodes"]["model.other.orders_assistant"] = {
        "unique_id": "model.other.orders_assistant",
        "resource_type": "model",
        "name": "orders_assistant",
        "database": "DB",
        "schema": "AGENTS",
        "alias": "ORDERS_ASSISTANT",
        "config": {"materialized": "cortex_agent"},
    }

    with pytest.raises(ValueError, match="model names must be unique"):
        select_agents(manifest)


def test_duplicate_model_physical_agent_fails_closed():
    manifest = _manifest()
    manifest["exposures"] = {}
    for logical_name in ("orders", "sales"):
        manifest["nodes"][f"model.consumer.{logical_name}"] = {
            "unique_id": f"model.consumer.{logical_name}",
            "resource_type": "model",
            "name": logical_name,
            "database": "DB",
            "schema": "AGENTS",
            "alias": "SHARED_AGENT",
            "config": {"materialized": "cortex_agent"},
        }

    with pytest.raises(ValueError, match="physical identities must be unique"):
        select_agents(manifest)


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

    assert assert_config_database(manifest, "db") == "DB"
    assert physical_agent_name(select_agents(manifest)[0], "sandbox") == "ORDERS_ASSISTANT"
    with pytest.raises(ValueError, match="does not match"):
        assert_config_database(manifest, "OTHER")
    with pytest.raises(ValueError, match="unquoted"):
        manifest["nodes"]["model.consumer.orders_assistant"]["alias"] = "BAD;DROP"
        agents = cortex_agents(manifest)
        physical_agent_name(agents[0], None)