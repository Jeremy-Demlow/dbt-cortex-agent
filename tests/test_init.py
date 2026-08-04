from __future__ import annotations

import subprocess
from argparse import Namespace

import pytest
import yaml

from dbt_cortex_agent import __version__
from dbt_cortex_agent.config import resolve_config
from dbt_cortex_agent.dbt_runner import CommandRunner
from dbt_cortex_agent.init import DEFAULT_REVISION, initialize


def _config(project_dir, target=None):
    return resolve_config(
        Namespace(
            project_dir=str(project_dir), manifest=None, target=target, connection=None,
            database=None, schema=None, role=None, warehouse=None, artifact_dir=None,
            dbt_executable="custom-dbt", snow_executable=None,
        ),
        env={},
    )


def _project(tmp_path, project_text="name: consumer\nversion: 1.0.0\nconfig-version: 2\n"):
    (tmp_path / "dbt_project.yml").write_text(project_text)
    return _config(tmp_path)


def test_init_preview_does_not_write(tmp_path):
    config = _project(tmp_path)
    original = (tmp_path / "dbt_project.yml").read_text()

    result = initialize(config, package_source="ssh://example/repo.git")

    assert not (tmp_path / "packages.yml").exists()
    assert (tmp_path / "dbt_project.yml").read_text() == original
    assert result.changed_files == ()
    assert "Preview only" in result.messages[0]


def test_init_defaults_to_installed_product_revision():
    assert DEFAULT_REVISION == f"v{__version__}"


def test_init_requires_package_source_without_existing_dependency(tmp_path):
    config = _project(tmp_path)

    with pytest.raises(ValueError, match="supply --package-source"):
        initialize(config)


def test_init_apply_adds_only_explicit_package_and_vars(tmp_path):
    config = _project(tmp_path)

    result = initialize(
        config,
        apply=True,
        package_source="ssh://example/repo.git",
        revision="v9",
        target="safe",
        allowed_targets=["qa", "safe"],
        allowed_databases=["DB", "AUDIT"],
        agent_schema="AGENT_OBJECTS",
        eval_schema="EVALUATIONS",
    )

    packages = yaml.safe_load((tmp_path / "packages.yml").read_text())
    project = yaml.safe_load((tmp_path / "dbt_project.yml").read_text())
    assert packages["packages"] == [{"git": "ssh://example/repo.git", "revision": "v9"}]
    assert project["vars"] == {
        "cortex_agent_deploy_target": "safe",
        "cortex_agent_allowed_targets": ["safe", "qa"],
        "cortex_agent_allowed_databases": ["DB", "AUDIT"],
        "cortex_agent_schema": "AGENT_OBJECTS",
        "cortex_eval_schema": "EVALUATIONS",
    }
    assert set(result.changed_files) == {tmp_path / "packages.yml", tmp_path / "dbt_project.yml"}


def test_init_apply_preserves_existing_yaml_text_and_comments(tmp_path):
    project_text = (
        "# consumer comment\nname: consumer\nversion: 1.0.0\nconfig-version: 2\n"
        "vars:\n  existing: keep  # inline comment\nmodels:\n  consumer: {}\n"
    )
    config = _project(tmp_path, project_text)
    packages_text = "# dependency comment\npackages:\n  - package: vendor/existing\n    version: 1.0.0\n"
    (tmp_path / "packages.yml").write_text(packages_text)

    initialize(config, apply=True, package_source="ssh://example/dbt-cortex-agent.git")

    updated_project = (tmp_path / "dbt_project.yml").read_text()
    updated_packages = (tmp_path / "packages.yml").read_text()
    assert updated_project == project_text
    assert updated_packages.startswith(packages_text)
    assert "ssh://example/dbt-cortex-agent.git" in updated_packages


def test_init_never_replaces_existing_package_or_vars(tmp_path):
    config = _project(
        tmp_path,
        "name: consumer\nversion: 1.0.0\nconfig-version: 2\nvars:\n"
        "  cortex_agent_deploy_target: protected\n"
        "  cortex_agent_allowed_databases: [PROTECTED_DB]\n"
        "  cortex_agent_schema: CUSTOM\n",
    )
    packages_text = "packages:\n  - git: ssh://example/repo.git\n    revision: v1\n"
    (tmp_path / "packages.yml").write_text(packages_text)

    initialize(
        config,
        apply=True,
        package_source="ssh://example/repo.git",
        revision="v2",
        target="new-target",
        allowed_databases=["NEW_DB"],
        agent_schema="NEW_SCHEMA",
    )

    project = yaml.safe_load((tmp_path / "dbt_project.yml").read_text())
    assert (tmp_path / "packages.yml").read_text() == packages_text
    assert project["vars"]["cortex_agent_deploy_target"] == "protected"
    assert project["vars"]["cortex_agent_allowed_databases"] == ["PROTECTED_DB"]
    assert project["vars"]["cortex_agent_schema"] == "CUSTOM"


def test_init_recognizes_existing_local_package(tmp_path):
    config = _project(tmp_path)
    original = "packages:\n  - local: ../dbt_cortex_agent\n"
    (tmp_path / "packages.yml").write_text(original)

    result = initialize(config, apply=True)

    assert (tmp_path / "packages.yml").read_text() == original
    assert result.changed_files == ()


def test_init_recognizes_existing_package_coordinate(tmp_path):
    config = _project(tmp_path)
    original = "packages:\n  - package: dbt_cortex_agent\n    version: 0.3.0\n"
    (tmp_path / "packages.yml").write_text(original)

    result = initialize(config, apply=True)

    assert (tmp_path / "packages.yml").read_text() == original
    assert result.changed_files == ()


def test_init_matches_git_only_when_source_is_explicit_and_exact(tmp_path):
    config = _project(tmp_path)
    fork = "ssh://fork.example/team/dbt-cortex-agent.git"
    original = f"packages:\n  - git: {fork}\n    revision: forked\n"
    (tmp_path / "packages.yml").write_text(original)

    with pytest.raises(ValueError, match="supply --package-source"):
        initialize(config)

    result = initialize(config, package_source=fork, apply=True)

    assert (tmp_path / "packages.yml").read_text() == original
    assert result.changed_files == ()


def test_init_does_not_add_deployment_or_schema_vars_without_explicit_options(tmp_path):
    config = _project(tmp_path)

    initialize(config, apply=True, package_source="ssh://example/repo.git")

    project = yaml.safe_load((tmp_path / "dbt_project.yml").read_text())
    assert "vars" not in project


def test_init_target_requires_adopter_database_allowlist(tmp_path):
    config = _project(tmp_path)

    with pytest.raises(ValueError, match="at least one --allow-database"):
        initialize(config, package_source="ssh://example/repo.git", target="safe")


def test_init_target_rejects_existing_empty_database_allowlist(tmp_path):
    config = _project(
        tmp_path,
        "name: consumer\nversion: 1.0.0\nconfig-version: 2\n"
        "vars:\n  cortex_agent_allowed_databases: []\n",
    )
    (tmp_path / "packages.yml").write_text("packages:\n  - local: ../dbt_cortex_agent\n")

    with pytest.raises(ValueError, match="at least one --allow-database"):
        initialize(config, target="safe")


def test_init_allowlists_require_explicit_target(tmp_path):
    config = _project(tmp_path)

    with pytest.raises(ValueError, match="require an explicit --target"):
        initialize(
            config,
            package_source="ssh://example/repo.git",
            allowed_databases=["DB"],
        )


def test_init_preview_describes_snippets_without_applying(tmp_path):
    config = _project(tmp_path)

    result = initialize(
        config,
        package_source="ssh://example/repo.git",
        target="safe",
        allowed_databases=["DB"],
        agent_schema="AGENTS",
    )

    output = "\n".join(result.messages)
    assert "append missing package snippet" in output
    assert f'revision: "v{__version__}"' in output
    assert "append missing var snippet" in output
    assert not (tmp_path / "packages.yml").exists()
    assert "vars:" not in (tmp_path / "dbt_project.yml").read_text()


def test_dbt_deps_requires_apply(tmp_path):
    config = _project(tmp_path)

    with pytest.raises(ValueError, match="requires --apply"):
        initialize(config, package_source="ssh://example/repo.git", run_deps=True)


def test_dbt_deps_runs_only_when_explicit(tmp_path):
    config = _project(tmp_path)
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "ok", "")

    runner = CommandRunner(fake_run)
    initialize(config, apply=True, package_source="ssh://example/repo.git", runner=runner)
    assert commands == []

    initialize(
        config,
        apply=True,
        package_source="ssh://example/repo.git",
        run_deps=True,
        runner=runner,
    )
    assert commands[0][0] == ["custom-dbt", "deps", "--project-dir", str(tmp_path)]