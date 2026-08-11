from __future__ import annotations

from argparse import Namespace

from dbt_cortex_agent.config import resolve_config


def _args(**values):
    defaults = {
        "project_dir": None, "manifest": None, "target": None, "connection": None,
        "database": None, "schema": None, "warehouse": None,
        "artifact_dir": None, "dbt_executable": None, "snow_executable": None,
    }
    return Namespace(**(defaults | values))


def test_config_resolves_project_relative_defaults(tmp_path):
    config = resolve_config(_args(project_dir=str(tmp_path)), env={})

    assert config.project_dir == tmp_path.resolve()
    assert config.manifest == (tmp_path / "target/manifest.json").resolve()
    assert config.artifact_dir == (tmp_path / "target/dbt_cortex_agent").resolve()
    assert config.dbt_executable == "dbt"
    assert config.snow_executable == "snow"
    assert config.target is None
    assert config.connection_explicit is False
    assert config.database_explicit is False
    assert config.warehouse_explicit is False


def test_explicit_config_wins_over_environment(tmp_path):
    config = resolve_config(
        _args(project_dir=str(tmp_path), target="explicit", database="CLI_DB"),
        env={"DBT_TARGET": "env", "SNOWFLAKE_DATABASE": "ENV_DB", "DBT_EXECUTABLE": "dbt2"},
    )

    assert config.target == "explicit"
    assert config.database == "CLI_DB"
    assert config.database_explicit is True
    assert config.dbt_executable == "dbt2"


def test_environment_supplies_shared_snowflake_options(tmp_path):
    config = resolve_config(
        _args(project_dir=str(tmp_path)),
        env={
            "SNOWFLAKE_CONNECTION_NAME": "conn", "SNOWFLAKE_SCHEMA": "S",
            "SNOWFLAKE_ROLE": "R", "SNOWFLAKE_WAREHOUSE": "W",
        },
    )

    assert (config.connection, config.schema, config.warehouse) == ("conn", "S", "W")
    assert not hasattr(config, "role")
    assert config.connection_explicit is False