from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .dbt_runner import CommandRunner


@dataclass(frozen=True)
class SnowflakeExecutionContext:
    connection_name: str
    account: str
    user: str
    database: str | None
    role: str | None
    warehouse: str | None
    authenticator: str
    dbt_env: Mapping[str, str]


def _required(parameters: Mapping[str, object], name: str, connection: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Snow CLI connection {connection!r} is missing required parameter {name!r}"
        )
    return value.strip()


def _connection_parameters(payload: object, connection: str) -> Mapping[str, object]:
    if not isinstance(payload, list):
        raise ValueError("Snow CLI connection list returned an invalid JSON document")
    for item in payload:
        if isinstance(item, dict) and item.get("connection_name") == connection:
            parameters = item.get("parameters")
            if not isinstance(parameters, dict):
                raise ValueError(f"Snow CLI connection {connection!r} has invalid parameters")
            return parameters
    raise ValueError(f"Snow CLI connection not found: {connection}")


def resolve_execution_context(
    *,
    connection: str,
    snow_executable: str,
    target: str | None,
    database: str | None,
    role: str | None,
    warehouse: str | None,
    parent_env: Mapping[str, str] | None = None,
    runner: CommandRunner | None = None,
) -> SnowflakeExecutionContext:
    command_runner = runner or CommandRunner()
    result = command_runner.run([snow_executable, "connection", "list", "--format", "json"])
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or result.stdout.strip()
            or f"Could not resolve Snow CLI connection {connection!r}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("Snow CLI connection list returned invalid JSON") from exc
    parameters = _connection_parameters(payload, connection)

    account = _required(parameters, "account", connection)
    user = _required(parameters, "user", connection)
    authenticator = _optional(parameters.get("authenticator"))
    strategy = (authenticator or "SNOWFLAKE_JWT").upper()
    if strategy not in {"SNOWFLAKE_JWT", "WORKLOAD_IDENTITY"}:
        raise ValueError(
            f"Snow CLI connection {connection!r} uses unsupported authenticator {strategy!r}; "
            "supported authenticators are SNOWFLAKE_JWT and WORKLOAD_IDENTITY"
        )
    unsupported = (
        "password",
        "token",
        "oauth_client_id",
        "oauth_client_secret",
        "private_key",
    )
    if any(_active_secret(parameters.get(name)) for name in unsupported):
        raise ValueError(
            f"Snow CLI connection {connection!r} contains an unsupported authentication parameter"
        )
    private_key_path: Path | None = None
    if strategy == "SNOWFLAKE_JWT":
        private_key = parameters.get("private_key_file") or parameters.get("private_key_path")
        if not isinstance(private_key, str) or not private_key.strip():
            raise ValueError(
                f"Snow CLI connection {connection!r} must use file-based key-pair authentication"
            )
        private_key_path = Path(private_key).expanduser()
        if not private_key_path.is_file():
            raise ValueError(
                f"Private key file configured for Snow CLI connection {connection!r} does not exist"
            )

    resolved_database = database or _optional(parameters.get("database"))
    resolved_warehouse = warehouse or _optional(parameters.get("warehouse"))
    resolved_role = role or _optional(parameters.get("role"))
    child_env = dict(os.environ if parent_env is None else parent_env)
    passphrase = child_env.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    values = {
        "SNOWFLAKE_ACCOUNT": account,
        "SNOWFLAKE_USER": user,
        "SNOWFLAKE_PRIVATE_KEY_PATH": str(private_key_path) if private_key_path else None,
        "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": passphrase,
        "SNOWFLAKE_DATABASE": resolved_database,
        "SNOWFLAKE_ROLE": resolved_role,
        "SNOWFLAKE_WAREHOUSE": resolved_warehouse,
        "DBT_TARGET": target,
    }
    for name, value in values.items():
        if value is not None:
            child_env[name] = value
        else:
            child_env.pop(name, None)

    return SnowflakeExecutionContext(
        connection_name=connection,
        account=account,
        user=user,
        database=resolved_database,
        role=resolved_role,
        warehouse=resolved_warehouse,
        authenticator=strategy,
        dbt_env=child_env,
    )


def _optional(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _active_secret(value: object) -> bool:
    normalized = _optional(value)
    return normalized is not None and normalized != "****"
