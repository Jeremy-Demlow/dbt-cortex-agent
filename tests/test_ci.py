from pathlib import Path
import re
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/package-check.yml"
RELEASE_WORKFLOW = ROOT / ".github/workflows/release.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _release_workflow_text() -> str:
    return RELEASE_WORKFLOW.read_text(encoding="utf-8")


def test_active_root_workflows_have_separate_package_and_release_triggers():
    workflows = sorted((ROOT / ".github/workflows").glob("*.yml")) + sorted(
        (ROOT / ".github/workflows").glob("*.yaml")
    )
    nested = sorted((ROOT / ".github/workflows").glob("**/*.yml")) + sorted(
        (ROOT / ".github/workflows").glob("**/*.yaml")
    )
    assert workflows == sorted([WORKFLOW, RELEASE_WORKFLOW])
    assert nested == workflows

    workflow = yaml.safe_load(_workflow_text())
    triggers = workflow[True]
    assert set(triggers) == {"pull_request", "push", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}

    release = yaml.safe_load(_release_workflow_text())
    release_triggers = release[True]
    assert set(release_triggers) == {"release", "workflow_dispatch"}
    assert release_triggers["release"] == {"types": ["published"]}
    assert "push" not in release_triggers
    assert "pull_request" not in release_triggers
    assert release["permissions"] == {"contents": "read"}


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
        "tests/test_materialization.py",
        "python -m build",
        "python -m twine check",
        "tests/verify_wheel.py",
        "scripts/verify_installed_wheel.py",
        "dbt-cortex-agent\" --help",
        "detect-secrets==1.5.0",
        "pip-licenses==5.5.0",
        "cyclonedx-bom==7.1.0",
        "python -m pip install --disable-pip-version-check dist/*.whl",
        "git status --porcelain",
    )
    assert all(value in text for value in required)


def test_dbt_matrix_runs_installed_wheel_verifier_for_both_supported_lines():
    workflow = yaml.safe_load(_workflow_text())
    compatibility = workflow["jobs"]["dbt-compatibility"]
    matrix = compatibility["strategy"]["matrix"]["include"]
    assert matrix == [
        {"line": "lower-bound", "dbt-core": "~=1.10.0", "dbt-snowflake": "1.10.3"},
        {"line": "authority", "dbt-core": "~=1.11.0", "dbt-snowflake": "1.11.4"},
    ]
    commands = "\n".join(step.get("run", "") for step in compatibility["steps"])
    assert 'python -m build --wheel --outdir "$RUNNER_TEMP/wheel-dist"' in commands
    assert "python scripts/verify_installed_wheel.py" in commands
    assert '--wheel "$RUNNER_TEMP"/wheel-dist/*.whl' in commands
    assert "--dbt-package-dir ." in commands
    assert "--dbt-core '${{ matrix.dbt-core }}'" in commands
    assert "--dbt-snowflake '${{ matrix.dbt-snowflake }}'" in commands


def test_current_product_versions_and_project_names_align():
    package = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = yaml.safe_load((ROOT / "dbt_project.yml").read_text(encoding="utf-8"))
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    init_source = (ROOT / "src/dbt_cortex_agent/__init__.py").read_text(encoding="utf-8")
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")

    assert package["project"]["name"].replace("-", "_") == project["name"]
    assert package["project"]["version"] == project["version"] == citation["version"] == "0.0.2"
    assert '__version__ = "0.0.2"' in init_source
    assert 'name = "dbt-cortex-agent"\nversion = "0.0.2"' in lock


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
    assert '(cd "$GITHUB_WORKSPACE" && xargs -0 detect-secrets scan)' in text
    assert "detect-secrets scan --all-files" not in text


def test_synthetic_immutable_sha_is_narrowly_allowlisted():
    source = (ROOT / "tests/test_doctor.py").read_text(encoding="utf-8")
    matching_lines = [
        line
        for line in source.splitlines()
        if "pragma: allowlist secret" in line
    ]

    assert len(matching_lines) == 1
    assert re.search(r'^SYNTHETIC_COMMIT_SHA = "[0-9a-f]{40}"', matching_lines[0])
    fixture_value = re.search(r'"([0-9a-f]{40})"', matching_lines[0]).group(1)
    assert source.count(fixture_value) == 1


def test_release_workflow_builds_and_checks_artifacts_before_upload():
    workflow = yaml.safe_load(_release_workflow_text())
    build = workflow["jobs"]["build"]
    assert "permissions" not in build
    steps = build["steps"]
    uses = [step.get("uses", "") for step in steps]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "actions/checkout@v7" in uses
    assert "actions/setup-python@v7" in uses
    assert "actions/upload-artifact@v7" in uses
    assert "build==1.3.0" in commands
    assert "twine==6.2.0" in commands
    assert "scripts/release_preflight.py" in commands
    assert "pytest -q" in commands
    assert "python -m build" in commands
    assert "python -m twine check dist/*" in commands
    assert "python tests/verify_wheel.py dist/*.whl" in commands


def test_release_publish_job_is_oidc_only_and_environment_protected():
    workflow = yaml.safe_load(_release_workflow_text())
    publish = workflow["jobs"]["publish"]
    assert publish["needs"] == "build"
    assert publish["environment"] == "pypi"
    assert publish["permissions"] == {"contents": "read", "id-token": "write"}
    assert "github.event_name == 'release'" in publish["if"]
    assert "github.event.action == 'published'" in publish["if"]
    assert "startsWith(github.event.release.tag_name, 'v')" in publish["if"]
    uses = [step.get("uses", "") for step in publish["steps"]]
    assert uses == ["actions/download-artifact@v8", "pypa/gh-action-pypi-publish@release/v1"]


def test_release_workflow_has_no_long_lived_pypi_credentials():
    text = _release_workflow_text().lower()
    forbidden = (
        "${{ secrets.",
        "pypi_api_token",
        "password:",
        "user:",
        "username:",
    )
    assert all(value not in text for value in forbidden)


def test_release_documentation_covers_trusted_publisher_and_checklist():
    text = (ROOT / "docs/guides/releasing.md").read_text(encoding="utf-8").lower()
    required = (
        "github oidc trusted publishing",
        "environment named exactly `pypi`",
        "github trusted publisher",
        "workflow: `release.yml`",
        "environment: `pypi`",
        "release checklist",
        "manual dispatch",
        "cannot publish",
        "vmajor.minor.patch",
        "post-publication",
    )
    assert all(value in text for value in required)