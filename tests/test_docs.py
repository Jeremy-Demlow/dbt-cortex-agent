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


def test_current_release_surfaces_identify_v030() -> None:
    for path in (
        README,
        ROOT / "pyproject.toml",
        ROOT / "docs/getting-started/installation.md",
        ROOT / "docs/reference/compatibility.md",
        CLI_REFERENCE,
        ROOT / "UPGRADING.md",
    ):
        assert "0.3.0" in path.read_text(encoding="utf-8"), path


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