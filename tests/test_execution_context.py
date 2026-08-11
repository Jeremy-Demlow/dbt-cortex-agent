from __future__ import annotations

import json
import os
import subprocess

import pytest

from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.execution_context import resolve_execution_context


class FakeSnow:
    def __init__(self, payload, returncode=0, stderr=""):
        self.payload = payload
        self.returncode = returncode
        self.stderr = stderr
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            self.returncode,
            json.dumps(self.payload) if self.returncode == 0 else "",
            self.stderr,
        )


def _payload(key_path, **overrides):
    parameters = {
        "account": "acct",
        "user": "user",
        "authenticator": "SNOWFLAKE_JWT",
        "private_key_file": str(key_path),
        "private_key_passphrase": "****",
        "database": "CONNECTION_DB",
        "role": "ROLE",
        "warehouse": "CONNECTION_WH",
    }
    parameters.update(overrides)
    return [{"connection_name": "named", "parameters": parameters}]


def test_resolves_key_pair_connection_into_isolated_dbt_environment(tmp_path, monkeypatch):
    key = tmp_path / "key.p8"
    key.write_text("not-a-real-key")
    monkeypatch.delenv("SNOWFLAKE_ACCOUNT", raising=False)
    fake = FakeSnow(_payload(key))

    context = resolve_execution_context(
        connection="named",
        snow_executable="snow-custom",
        target="sandbox",
        database="CLI_DB",
        warehouse="CLI_WH",
        parent_env={"KEEP": "yes", "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "real-passphrase"},
        runner=CommandRunner(fake),
    )

    assert fake.calls[0][0] == ["snow-custom", "connection", "list", "--format", "json"]
    assert context.database == "CLI_DB"
    assert context.warehouse == "CLI_WH"
    assert context.dbt_env == {
        "KEEP": "yes",
        "SNOWFLAKE_ACCOUNT": "acct",
        "SNOWFLAKE_USER": "user",
        "SNOWFLAKE_PRIVATE_KEY_PATH": str(key),
        "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "real-passphrase",
        "SNOWFLAKE_DATABASE": "CLI_DB",
        "SNOWFLAKE_ROLE": "ROLE",
        "SNOWFLAKE_WAREHOUSE": "CLI_WH",
        "DBT_TARGET": "sandbox",
    }
    assert "SNOWFLAKE_ACCOUNT" not in os.environ


def test_missing_connection_fails_without_leaking_parameters(tmp_path):
    key = tmp_path / "key.p8"
    key.write_text("not-a-real-key")

    with pytest.raises(ValueError, match="Snow CLI connection not found: other") as exc:
        resolve_execution_context(
            connection="other",
            snow_executable="snow",
            target=None,
            database=None,
            warehouse=None,
            parent_env={},
            runner=CommandRunner(FakeSnow(_payload(key))),
        )

    assert "****" not in str(exc.value)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"account": ""}, "missing required parameter 'account'"),
        ({"user": ""}, "missing required parameter 'user'"),
        ({"private_key_file": None}, "file-based key-pair authentication"),
        ({"authenticator": None}, "must use authenticator SNOWFLAKE_JWT"),
        ({"authenticator": "externalbrowser"}, "must use authenticator SNOWFLAKE_JWT"),
        ({"password": "active-password"}, "unsupported authentication parameter"),
        ({"private_key": "inline-key"}, "unsupported authentication parameter"),
    ],
)
def test_rejects_incomplete_or_unsupported_connection(tmp_path, overrides, message):
    key = tmp_path / "key.p8"
    key.write_text("not-a-real-key")

    with pytest.raises(ValueError, match=message):
        resolve_execution_context(
            connection="named",
            snow_executable="snow",
            target=None,
            database=None,
            warehouse=None,
            parent_env={},
            runner=CommandRunner(FakeSnow(_payload(key, **overrides))),
        )


def test_masked_passphrase_is_never_forwarded(tmp_path):
    key = tmp_path / "key.p8"
    key.write_text("not-a-real-key")
    context = resolve_execution_context(
        connection="named",
        snow_executable="snow",
        target=None,
        database=None,
        warehouse=None,
        parent_env={},
        runner=CommandRunner(FakeSnow(_payload(key))),
    )

    assert "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE" not in context.dbt_env