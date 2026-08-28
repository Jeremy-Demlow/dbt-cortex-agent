from __future__ import annotations

import json
import os
import subprocess

import pytest

# Evidence: TC-022-03 TC-022-04
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
        role="CLI_ROLE",
        warehouse="CLI_WH",
        parent_env={
            "KEEP": "yes",
            "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "real-passphrase",  # pragma: allowlist secret
        },
        runner=CommandRunner(fake),
    )

    assert fake.calls[0][0] == ["snow-custom", "connection", "list", "--format", "json"]
    assert context.database == "CLI_DB"
    assert context.warehouse == "CLI_WH"
    assert context.role == "CLI_ROLE"
    assert context.authenticator == "SNOWFLAKE_JWT"
    assert context.dbt_env == {
        "KEEP": "yes",
        "SNOWFLAKE_ACCOUNT": "acct",
        "SNOWFLAKE_USER": "user",
        "SNOWFLAKE_PRIVATE_KEY_PATH": str(key),
        "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "real-passphrase",  # pragma: allowlist secret
        "SNOWFLAKE_DATABASE": "CLI_DB",
        "SNOWFLAKE_ROLE": "CLI_ROLE",
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
            role=None,
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
        ({"authenticator": "externalbrowser"}, "unsupported authenticator"),
        ({"authenticator": "oauth"}, "unsupported authenticator"),
        ({"authenticator": "username_password_mfa"}, "unsupported authenticator"),
        (
            {"password": "active-password"},
            "unsupported authentication parameter",
        ),  # pragma: allowlist secret
        (
            {"private_key": "inline-key"},
            "unsupported authentication parameter",
        ),  # pragma: allowlist secret
        (
            {"token": "active-token"},
            "unsupported authentication parameter",
        ),  # pragma: allowlist secret
        (
            {"oauth_client_id": "client-id"},
            "unsupported authentication parameter",
        ),  # pragma: allowlist secret
        (
            {"oauth_client_secret": "client-secret"},
            "unsupported authentication parameter",
        ),  # pragma: allowlist secret
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
            role=None,
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
        role=None,
        warehouse=None,
        parent_env={},
        runner=CommandRunner(FakeSnow(_payload(key))),
    )

    assert "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE" not in context.dbt_env


@pytest.mark.parametrize(
    "parameter",
    ["password", "token", "oauth_client_id", "oauth_client_secret", "private_key"],
)
def test_masked_unsupported_parameters_are_inactive(tmp_path, parameter):
    key = tmp_path / "key.p8"
    key.write_text("not-a-real-key")

    context = resolve_execution_context(
        connection="named",
        snow_executable="snow",
        target="sandbox",
        database=None,
        role=None,
        warehouse=None,
        parent_env={},
        runner=CommandRunner(FakeSnow(_payload(key, **{parameter: "****"}))),
    )

    assert context.authenticator == "SNOWFLAKE_JWT"


def test_missing_key_file_is_rejected_before_child_execution(tmp_path):
    missing = tmp_path / "missing.p8"
    with pytest.raises(ValueError, match="does not exist"):
        resolve_execution_context(
            connection="named",
            snow_executable="snow",
            target="sandbox",
            database=None,
            role=None,
            warehouse=None,
            parent_env={},
            runner=CommandRunner(FakeSnow(_payload(missing))),
        )


def test_workload_identity_connection_is_accepted_without_private_key(tmp_path):
    payload = _payload(
        tmp_path / "unused.p8",
        authenticator="WORKLOAD_IDENTITY",
        workload_identity_provider="OIDC",
        private_key_file=None,
    )

    context = resolve_execution_context(
        connection="named",
        snow_executable="snow",
        target="sandbox",
        database="DB",
        role="ROLE_OVERRIDE",
        warehouse="WH",
        parent_env={"SNOWFLAKE_PRIVATE_KEY_PATH": "/ambient/key"},
        runner=CommandRunner(FakeSnow(payload)),
    )

    assert context.authenticator == "WORKLOAD_IDENTITY"
    assert context.role == "ROLE_OVERRIDE"
    assert "SNOWFLAKE_PRIVATE_KEY_PATH" not in context.dbt_env
