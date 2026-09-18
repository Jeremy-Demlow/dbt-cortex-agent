from __future__ import annotations

import json
import subprocess
from argparse import Namespace
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from dbt_cortex_agent.commands.common import fresh_manifest
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner

# Evidence: TC-032-04
MANIFEST = {
    "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
    "nodes": {},
}


def config_for(tmp_path, manifest=None, env=None):
    return resolve_config(
        Namespace(project_dir=str(tmp_path), manifest=manifest, target="sandbox"),
        env=env or {},
    )


@pytest.mark.parametrize(
    "location", ["target/manifest.json", "artifacts/dbt/manifest.json", "absolute"]
)
def test_fresh_parse_consumes_exact_output(tmp_path, location):
    requested = str(tmp_path / "outside/manifest.json") if location == "absolute" else location
    config = config_for(tmp_path, requested)
    config.manifest.parent.mkdir(parents=True)
    config.manifest.write_text(json.dumps({**MANIFEST, "stale": True}))
    profile_env = {
        "DBT_PROFILES_DIR": "relative/profiles",
        "DBT_TARGET_PATH": "wrong",
        "DBT_WRITE_JSON": "false",
    }
    config = replace(config, execution_context=SimpleNamespace(dbt_env=profile_env))
    calls = []

    def parse(command, **kwargs):
        calls.append((command, kwargs))
        output = Path(command[command.index("--target-path") + 1]) / "manifest.json"
        output.write_text(json.dumps(MANIFEST))
        return subprocess.CompletedProcess(command, 0, "", "")

    assert fresh_manifest(config, no_parse=False, runner=CommandRunner(parse)) == MANIFEST
    command, kwargs = calls[0]
    assert command == [
        "dbt",
        "parse",
        "--project-dir",
        str(tmp_path),
        "--target",
        "sandbox",
        "--target-path",
        str(config.manifest.parent),
        "--write-json",
    ]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["env"] == profile_env
    assert profile_env["DBT_TARGET_PATH"] == "wrong"


@pytest.mark.parametrize(
    "explicit,environment,project_path,expected",
    [
        (None, {}, None, "target"),
        (None, {}, "project-artifacts", "project-artifacts"),
        (None, {"DBT_TARGET_PATH": "env-artifacts"}, "project-artifacts", "env-artifacts"),
        (
            None,
            {"DBT_MANIFEST": "selected/manifest.json", "DBT_TARGET_PATH": "env"},
            "project",
            "selected",
        ),
        (
            "explicit/manifest.json",
            {"DBT_MANIFEST": "selected/manifest.json"},
            "project",
            "explicit",
        ),
    ],
)
def test_manifest_location_precedence(tmp_path, explicit, environment, project_path, expected):
    if project_path is not None:
        (tmp_path / "dbt_project.yml").write_text(f"target-path: {project_path}\n")
    config = config_for(tmp_path, explicit, environment)
    assert config.manifest == tmp_path / expected / "manifest.json"


def test_absolute_environment_target_path(tmp_path):
    output = tmp_path / "external"
    config = config_for(tmp_path, env={"DBT_TARGET_PATH": str(output)})
    assert config.manifest == output / "manifest.json"


@pytest.mark.parametrize("target_path", ["\"{{ env_var('BUILD_PATH') }}\"", "[]", "null", '""'])
def test_ambiguous_project_target_path_requires_explicit_manifest(tmp_path, target_path):
    (tmp_path / "dbt_project.yml").write_text(f"target-path: {target_path}\n")
    with pytest.raises(ValueError, match="Ambiguous dbt target-path"):
        config_for(tmp_path)
    assert config_for(tmp_path, "exact/manifest.json").manifest == tmp_path / "exact/manifest.json"
    assert (
        config_for(tmp_path, env={"DBT_TARGET_PATH": "env"}).manifest
        == tmp_path / "env/manifest.json"
    )


def test_nonstandard_manifest_filename_rejected_before_parse(tmp_path):
    config = config_for(tmp_path, "snapshot.json")
    runner = CommandRunner(lambda *args, **kwargs: pytest.fail("ambiguous parse invoked"))
    with pytest.raises(ValueError, match="requires --manifest"):
        fresh_manifest(config, no_parse=False, runner=runner)


@pytest.mark.parametrize("existing", [False, True])
def test_parse_without_output_never_consumes_stale_manifest(tmp_path, existing):
    config = config_for(tmp_path, "custom/manifest.json")
    if existing:
        config.manifest.parent.mkdir()
        config.manifest.write_text(json.dumps(MANIFEST))
    runner = CommandRunner(
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", "")
    )
    with pytest.raises(RuntimeError, match="did not produce a fresh manifest"):
        fresh_manifest(config, no_parse=False, runner=runner)


def test_parse_failure_does_not_consume_existing_manifest(tmp_path):
    config = config_for(tmp_path, "manifest.json")
    config.manifest.write_text(json.dumps(MANIFEST))
    runner = CommandRunner(
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "parse failed")
    )
    with pytest.raises(RuntimeError, match="parse failed"):
        fresh_manifest(config, no_parse=False, runner=runner)


def test_no_parse_remains_explicit_fixture_escape_hatch(tmp_path):
    config = config_for(tmp_path, "snapshot.json")
    config.manifest.write_text(json.dumps(MANIFEST))
    runner = CommandRunner(lambda *args, **kwargs: pytest.fail("no-parse invoked dbt"))
    assert fresh_manifest(config, no_parse=True, runner=runner) == MANIFEST


def test_ambient_profile_path_is_inherited_with_project_cwd(tmp_path, monkeypatch):
    monkeypatch.setenv("DBT_PROFILES_DIR", "relative/profiles")
    config = config_for(tmp_path)

    def parse(command, **kwargs):
        assert "env" not in kwargs
        assert kwargs["cwd"] == tmp_path
        output = Path(command[command.index("--target-path") + 1]) / "manifest.json"
        output.parent.mkdir()
        output.write_text(json.dumps(MANIFEST))
        return subprocess.CompletedProcess(command, 0, "", "")

    assert fresh_manifest(config, no_parse=False, runner=CommandRunner(parse)) == MANIFEST
