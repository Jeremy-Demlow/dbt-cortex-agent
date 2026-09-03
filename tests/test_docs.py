import argparse
import re
import shlex
from pathlib import Path

from dbt_cortex_agent.cli import build_parser

# Evidence: TC-028-01 TC-028-03 TC-028-04 TC-028-05 TC-028-07

ROOT = Path(__file__).parents[1]


def _command_paths(parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()) -> set[str]:
    paths: set[str] = set()
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, child in action.choices.items():
            path = (*prefix, name)
            if any(isinstance(item, argparse._SubParsersAction) for item in child._actions):
                paths.update(_command_paths(child, path))
            else:
                paths.add(" ".join(path))
    return paths


def _bash_blocks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"```(?:bash|shell)\n(.*?)```", text, flags=re.DOTALL)


def _documented_cli_commands(path: Path) -> list[list[str]]:
    commands: list[list[str]] = []
    for block in _bash_blocks(path):
        logical = block.replace("\\\n", " ")
        for line in logical.splitlines():
            line = line.strip()
            if not line.startswith("dbt-cortex-agent "):
                continue
            line = re.sub(r"<[^>]+>", "placeholder.json", line)
            commands.append(shlex.split(line))
    return commands


def test_active_docs_describe_v001_materialization_boundary():
    paths = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "docs/concepts/ownership-boundary.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "0.0.7" in combined
    assert "dbt build --select" in combined
    assert "Python must not render, create, alter, commit, alias, grant, promote" in combined
    assert "Legacy exposure declarations remain supported" not in combined
    assert "UPGRADING.md" not in combined


def test_readme_documents_package_agent_commands():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "`agent smoke`" in readme
    assert "`agent deploy`" in readme
    assert "`agent promote`" in readme
    assert "`agent rollback`" in readme
    for removed in ("`agent render`", "`agent grant`"):
        assert removed not in readme


def test_changelog_starts_public_history_at_v001():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## 0.0.7 — 2026-09-03" in changelog
    for old in ("## 0.1.0", "## 0.2.0", "## 0.3.0", "## 0.3.1"):
        assert old not in changelog


def test_customer_workflow_docs_require_no_adopter_wrappers():
    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "README.md",
            ROOT / "docs/getting-started/quickstart.md",
            ROOT / "docs/guides/evaluations.md",
            ROOT / "docs/reference/cli.md",
        )
    )

    assert "agent deploy" in docs
    assert "eval verify" in docs
    assert "project_runner.py" not in docs
    assert "agent_gate.py" not in docs
    assert "make dbt-focus" not in docs


def test_no_upgrade_guide_is_shipped_before_first_release():
    assert not (ROOT / "UPGRADING.md").exists()


def test_cli_reference_covers_every_shipped_command_path():
    reference = (ROOT / "docs/reference/cli.md").read_text(encoding="utf-8")

    for path in _command_paths(build_parser()):
        assert f"dbt-cortex-agent {path}" in reference, path

    assert "eval migrate-baseline" not in reference


def test_canonical_developer_guide_commands_parse_with_shipped_cli():
    path = ROOT / "docs/guides/developer-ci-workflow.md"
    commands = _documented_cli_commands(path)

    assert len(commands) >= 10
    parser = build_parser()
    for command in commands:
        parser.parse_args(command[1:])


def test_documentation_relative_links_resolve():
    paths = [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]
    failures: list[str] = []
    pattern = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")

    for path in paths:
        for target in pattern.findall(path.read_text(encoding="utf-8")):
            clean = target.split("#", 1)[0]
            if not clean or "://" in clean or clean.startswith("mailto:"):
                continue
            if not (path.parent / clean).resolve().exists():
                failures.append(f"{path.relative_to(ROOT)} -> {target}")

    assert not failures, "Broken relative links:\n" + "\n".join(failures)


def test_non_mutating_quickstart_has_no_applied_remote_command():
    path = ROOT / "docs/getting-started/quickstart.md"
    remote_commands = (
        "agent deploy",
        "agent smoke",
        "skill upload",
        "skill smoke",
        "eval run",
        "eval verify",
    )

    for command in _documented_cli_commands(path):
        rendered = " ".join(command)
        if any(name in rendered for name in remote_commands):
            assert "--apply" not in command


def test_current_release_identity_is_consistent_across_public_docs():
    expected = "0.0.7"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    installation = (ROOT / "docs/getting-started/installation.md").read_text(encoding="utf-8")
    cli_reference = (ROOT / "docs/reference/cli.md").read_text(encoding="utf-8")

    for text in (readme, installation):
        assert f"dbt-cortex-agent[runtime]=={expected}" in text
        assert f"revision: v{expected}" in text
    assert cli_reference.startswith(f"# CLI reference (v{expected})")
