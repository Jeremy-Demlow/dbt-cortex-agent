from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_active_docs_describe_v001_materialization_boundary():
    paths = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "docs/concepts/ownership-boundary.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "0.0.1" in combined
    assert "dbt build --select" in combined
    assert "Python must not render, create, alter, commit, alias, grant, promote" in combined
    assert "Legacy exposure declarations remain supported" not in combined
    assert "UPGRADING.md" not in combined


def test_readme_documents_only_retained_python_agent_command():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "`agent smoke`" in readme
    for removed in (
        "`agent render`",
        "`agent deploy`",
        "`agent grant`",
        "`agent promote`",
        "`agent rollback`",
    ):
        assert removed not in readme


def test_changelog_starts_public_history_at_v001():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## 0.0.1 — 2026-08-18" in changelog
    for old in ("## 0.1.0", "## 0.2.0", "## 0.3.0", "## 0.3.1"):
        assert old not in changelog


def test_no_upgrade_guide_is_shipped_before_first_release():
    assert not (ROOT / "UPGRADING.md").exists()