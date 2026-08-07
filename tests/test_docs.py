from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest
import yaml

from dbt_cortex_agent.cli import build_parser


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CLI_REFERENCE = ROOT / "docs/reference/cli.md"
ADOPTER_DOCS = [
    README,
    ROOT / "UPGRADING.md",
    ROOT / "integration_tests/README.md",
    *sorted((ROOT / "docs").rglob("*.md")),
    *sorted((ROOT / "integration_tests/docs").rglob("*.md")),
]
POLICY_FILES = [
    README,
    ROOT / "CONTRIBUTING.md",
    ROOT / "CODE_OF_CONDUCT.md",
    ROOT / "SUPPORT.md",
    ROOT / "THIRD_PARTY_LICENSES.md",
    ROOT / "CITATION.cff",
    ROOT / ".github/PULL_REQUEST_TEMPLATE.md",
    ROOT / ".github/CODEOWNERS",
]
REQ_011 = ROOT / "requirements/REQ-011_tutorial_product_readiness.md"


def _parser_contract() -> tuple[set[str], set[str]]:
    commands: set[str] = set()
    options: set[str] = set()

    def walk(parser, prefix: tuple[str, ...] = ()) -> None:
        for action in parser._actions:
            options.update(action.option_strings)
            if action.__class__.__name__ == "_SubParsersAction":
                for name, child in action.choices.items():
                    path = (*prefix, name)
                    commands.add(" ".join(path))
                    walk(child, path)

    walk(build_parser())
    return commands, options


def _markdown_links(path: Path) -> list[str]:
    return re.findall(r"(?<!!)\[[^]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8"))


def _fenced_blocks(path: Path, language: str) -> list[str]:
    pattern = rf"```{language}\n(.*?)\n```"
    return re.findall(pattern, path.read_text(encoding="utf-8"), flags=re.DOTALL)


def test_cli_reference_covers_parser_commands_and_options() -> None:
    commands, options = _parser_contract()
    text = CLI_REFERENCE.read_text(encoding="utf-8")
    for command in commands:
        assert f"dbt-cortex-agent {command}" in text
    for option in options:
        assert f"`{option}`" in text


@pytest.mark.parametrize("path", ADOPTER_DOCS, ids=lambda path: str(path.relative_to(ROOT)))
def test_local_markdown_links_exist(path: Path) -> None:
    for target in _markdown_links(path):
        if target.startswith(("http://", "https://", "mailto:")) or target.startswith("#"):
            continue
        relative = target.split("#", 1)[0]
        if relative:
            assert (path.parent / relative).resolve().exists(), f"broken link in {path}: {target}"


def test_adopter_docs_remove_stale_release_language() -> None:
    stale = (
        "copyable tooling",
        "copied tooling",
        "copyable python",
        "embedded-package",
        "make dbt-focus-",
        "after the v0.3.0 tag is pushed",
        "optional framework tooling",
    )
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in ADOPTER_DOCS)
    for phrase in stale:
        assert phrase not in text


def test_project_policy_is_simple_and_maintainer_led() -> None:
    assert not (ROOT / "GOVERNANCE.md").exists()
    assert not (ROOT / "MAINTAINERS.md").exists()

    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in POLICY_FILES)
    forbidden = (
        "two-maintainer",
        "two distinct maintainers",
        "second maintainer",
        "vacant role",
        "employer-rights",
        "applicable employer",
        "legal review",
        "publication blocked",
        "blocks publication",
        "governance.md",
        "maintainers.md",
    )
    assert all(phrase not in text for phrase in forbidden)
    assert "maintainer-led" in text


def test_project_policy_retains_license_security_and_support_contracts() -> None:
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    pull_request = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8").lower()
    support = (ROOT / "SUPPORT.md").read_text(encoding="utf-8").lower()
    codeowners = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8")

    assert "Apache License 2.0 Section 5" in contributing
    assert "right to license" in contributing
    assert "Apache-2.0 Section 5" in pull_request
    assert "email" in security
    assert "do not open a public issue" in security
    assert "best effort" in support
    assert "@Jeremy-Demlow" in codeowners
    assert "GOVERNANCE.md" not in codeowners
    assert "MAINTAINERS.md" not in codeowners


def test_req_011_contracts_additive_tutorial_product_readiness() -> None:
    text = REQ_011.read_text(encoding="utf-8").lower()
    headings = (
        "## summary",
        "## business context",
        "## objective",
        "## acceptance criteria",
        "## user stories",
        "## dependencies",
        "## out of scope",
        "## notes",
    )
    required = (
        "documentation defects",
        "deterministic orders starter",
        "not a generic project or agent wizard",
        "projection-aware",
        "general agent smoke",
        "backward-compatibility",
        "non-mutating by default",
        "package completion gate",
        "skill for the tutorial is deferred",
        "no snowflake connection",
        "explicit operator opt-in",
    )

    assert all(heading in text for heading in headings)
    assert all(phrase in text for phrase in required)
    assert "implementation begins" in text


def test_general_agent_smoke_contract_is_documented() -> None:
    cli = CLI_REFERENCE.read_text(encoding="utf-8")
    lifecycle = (ROOT / "docs/guides/lifecycle.md").read_text(encoding="utf-8")

    for phrase in (
        "agent smoke",
        "--question",
        "--projection canonical|native_eval",
        "--expect-tool",
        "--agent-object",
        "--endpoint",
        "does not construct a connector or invoke the Agent",
        "preview sets the final two fields to\n`null`",
        "failures exit `2`",
    ):
        assert phrase in cli
    assert "General smoke is separate from skill smoke" in lifecycle
    assert "custom evaluation suffix is never guessed" in lifecycle
    assert "reuses the existing invocation/SSE client" in lifecycle


def test_current_release_surfaces_identify_v031() -> None:
    for path in (
        README,
        ROOT / "pyproject.toml",
        ROOT / "docs/getting-started/installation.md",
        ROOT / "docs/reference/compatibility.md",
        CLI_REFERENCE,
        ROOT / "UPGRADING.md",
    ):
        assert "0.3.1" in path.read_text(encoding="utf-8"), path


def test_public_dual_surface_install_contract() -> None:
    readme = README.read_text(encoding="utf-8")
    installation = (ROOT / "docs/getting-started/installation.md").read_text(encoding="utf-8")
    upgrading = (ROOT / "UPGRADING.md").read_text(encoding="utf-8")
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    combined = "\n".join((readme, installation, upgrading))
    public_source = "https://github.com/Jeremy-Demlow/dbt-cortex-agent.git"
    primary_install = "pipx install 'dbt-cortex-agent[runtime]==0.3.1'"

    assert all(public_source in text for text in (readme, installation, upgrading, metadata))
    assert all(primary_install in text for text in (readme, installation, upgrading))
    assert "python -m pip install 'dbt-cortex-agent[runtime]==0.3.1'" in combined
    assert "dbt deps` does not install" in combined
    assert "same immutable" in combined
    assert "doctor" in combined and "align" in combined
    assert "after v0.3.1 is published to pypi" in combined.lower()
    assert all("/absolute/path/to/dbt-cortex-agent[runtime]" in text for text in (readme, installation, upgrading))
    assert "clean local checkout" in combined.lower()


def test_adopter_and_fixture_surfaces_reject_private_install_references() -> None:
    paths = [
        README,
        ROOT / "UPGRADING.md",
        ROOT / "pyproject.toml",
        *sorted((ROOT / "docs").rglob("*.md")),
        *(path for path in sorted((ROOT / "tests").glob("*.py")) if path != Path(__file__)),
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
    forbidden = (
        "git@" + "github.com",
        "ssh" + "://",
        "private git",
        "private " + "index",
        "configured private python",
        "approved release " + "source",
    )
    assert all(phrase not in text for phrase in forbidden)


def test_quickstart_cli_examples_parse_and_do_not_cross_apply_boundaries() -> None:
    path = ROOT / "docs/getting-started/quickstart.md"
    blocks = _fenced_blocks(path, "bash")
    commands: list[list[str]] = []
    for block in blocks:
        logical = block.replace("\\\n", " ")
        for line in logical.splitlines():
            line = line.strip()
            if line.startswith("dbt-cortex-agent "):
                commands.append(shlex.split(line)[1:])
    assert commands
    parser = build_parser()
    for command in commands:
        assert "--apply" not in command
        try:
            parser.parse_args(command)
        except SystemExit as exc:
            assert exc.code == 0


@pytest.mark.parametrize(
    "path",
    [README, ROOT / "integration_tests/README.md", *sorted((ROOT / "docs").rglob("*.md"))],
    ids=lambda path: str(path.relative_to(ROOT)),
)
def test_single_line_cli_examples_parse(path: Path) -> None:
    parser = build_parser()
    for block in _fenced_blocks(path, "bash"):
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("dbt-cortex-agent ") and not line.endswith("\\"):
                try:
                    parser.parse_args(shlex.split(line)[1:])
                except SystemExit as exc:
                    assert exc.code == 0


def test_yaml_examples_parse_and_preserve_metadata_contracts() -> None:
    path = ROOT / "docs/guides/configuration-model.md"
    documents = [yaml.safe_load(block) for block in _fenced_blocks(path, "yaml")]
    exposure_doc = next(doc for doc in documents if isinstance(doc, dict) and "exposures" in doc)
    eval_doc = next(doc for doc in documents if isinstance(doc, dict) and "models" in doc)
    agent = exposure_doc["exposures"][0]["config"]["meta"]["cortex_agent"]
    suite = eval_doc["models"][0]["config"]["meta"]["cortex_eval"]
    assert agent["enabled"] is True
    assert agent["snowflake_name"]
    assert agent["tools"]
    assert suite["agent"] == exposure_doc["exposures"][0]["name"]
    assert suite["projection"] in {"canonical", "native_eval"}
    assert suite["metrics"] and suite["questions"]


def test_evaluation_prerequisites_are_explicit() -> None:
    text = (ROOT / "docs/guides/evaluations.md").read_text(encoding="utf-8").lower()
    for phrase in ("materialized eval table", "evaluation stage", "deployed native-eval agent"):
        assert phrase in text
    assert "does not create these prerequisites" in text
    assert "explicit `--connection` and\n`--warehouse`" in text


def test_v030_docs_state_current_scaffolding_deploy_and_output_boundaries() -> None:
    installation = (ROOT / "docs/getting-started/installation.md").read_text(encoding="utf-8")
    lifecycle = (ROOT / "docs/guides/lifecycle.md").read_text(encoding="utf-8")
    evaluations = (ROOT / "docs/guides/evaluations.md").read_text(encoding="utf-8")
    troubleshooting = (ROOT / "docs/troubleshooting.md").read_text(encoding="utf-8")

    assert "Install Snow CLI" in installation
    assert "does not\ncreate Agent exposure YAML" in installation
    assert "uploads them with Snow CLI\nbefore it invokes `cortex_agent__deploy`" in lifecycle
    assert "returns\nthe actual specification" in lifecycle
    assert "<artifact-dir>/renders/<target>/<agent>/<projection>.json" in lifecycle
    assert "--agent orders_assistant --projection native_eval" in evaluations
    assert "retains all normal mutation gates" in evaluations
    assert "candidates/<agent>/<suite>/<run_name>.json" in evaluations
    assert "baselines/<agent>/<suite>.json" in evaluations
    assert "Use this sequence" in troubleshooting


def test_integration_fixture_has_explicit_database_allowlist() -> None:
    project = yaml.safe_load((ROOT / "integration_tests/dbt_project.yml").read_text(encoding="utf-8"))
    assert project["vars"]["cortex_agent_allowed_databases"] == ["AM_SKI_RESORT_DBT_FOCUS"]