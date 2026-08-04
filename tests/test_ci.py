from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/package-check.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_one_active_root_package_workflow_has_required_triggers_and_permissions():
    workflows = sorted((ROOT / ".github/workflows").glob("*.yml")) + sorted(
        (ROOT / ".github/workflows").glob("*.yaml")
    )
    nested = sorted((ROOT / ".github/workflows").glob("**/*.yml")) + sorted(
        (ROOT / ".github/workflows").glob("**/*.yaml")
    )
    assert workflows == [WORKFLOW]
    assert nested == workflows

    workflow = yaml.safe_load(_workflow_text())
    triggers = workflow[True]
    assert set(triggers) == {"pull_request", "push", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}


def test_workflow_is_credential_free_non_mutating_and_non_spend():
    text = _workflow_text().lower()
    forbidden = (
        "${{ secrets.",
        "snowflake_password",
        "snowflake_private_key:",
        "snowflake_private_key_path: ${{",
        "--apply",
        "accept-baseline",
        "skill smoke",
        "connection test",
        "eval run --apply",
    )
    assert all(value not in text for value in forbidden)
    assert "permissions:\n  contents: read" in text


def test_python_and_dbt_matrices_match_declared_compatibility():
    text = _workflow_text()
    package = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = yaml.safe_load((ROOT / "dbt_project.yml").read_text(encoding="utf-8"))

    assert package["project"]["requires-python"] == ">=3.10,<4"
    assert '["3.10", "3.11", "3.12", "3.13"]' in text
    assert project["require-dbt-version"] == [">=1.10.0", "<2.0.0"]
    for value in ('dbt-core: "~=1.10.0"', 'dbt-snowflake: "1.10.3"', 'dbt-core: "~=1.11.0"', 'dbt-snowflake: "1.11.4"'):
        assert value in text


def test_workflow_covers_release_and_deterministic_contracts():
    text = _workflow_text()
    required = (
        "tests/test_docs.py tests/test_ci.py",
        "python -m compileall",
        "pytest -q",
        "dbt deps",
        "dbt parse",
        "tests/test_eval_plan_macros.py",
        "tests/test_deploy.py",
        "python -m build",
        "python -m twine check",
        "tests/verify_wheel.py",
        "dbt-cortex-agent\" --help",
        "detect-secrets==1.5.0",
        "pip-licenses==5.5.0",
        "cyclonedx-bom==7.1.0",
        "python -m pip install --disable-pip-version-check dist/*.whl",
        "git status --porcelain",
    )
    assert all(value in text for value in required)


def test_current_product_versions_and_project_names_align():
    package = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = yaml.safe_load((ROOT / "dbt_project.yml").read_text(encoding="utf-8"))
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    init_source = (ROOT / "src/dbt_cortex_agent/__init__.py").read_text(encoding="utf-8")
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")

    assert package["project"]["name"].replace("-", "_") == project["name"]
    assert package["project"]["version"] == project["version"] == citation["version"] == "0.3.0"
    assert '__version__ = "0.3.0"' in init_source
    assert 'name = "dbt-cortex-agent"\nversion = "0.3.0"' in lock


def test_generated_residue_is_ignored_or_cleaned_by_workflow():
    text = _workflow_text()
    for value in (
        "rm -rf integration_tests/dbt_packages integration_tests/target integration_tests/logs",
        "rm -rf build dist src/*.egg-info",
        "rm -rf .pytest_cache",
        "__pycache__",
    ):
        assert value in text


def test_secret_scan_is_limited_to_tracked_non_lock_files():
    text = _workflow_text()
    assert "git ls-files -z -- ':!:*lock*'" in text
    assert "detect-secrets scan --all-files" not in text