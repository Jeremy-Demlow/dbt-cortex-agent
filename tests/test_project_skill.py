from __future__ import annotations

from pathlib import Path
import re
import shlex
import shutil
import subprocess

import pytest
import yaml

from dbt_cortex_agent.cli import build_parser


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".cortex/skills"
SKILL = SKILL_ROOT / "dbt-cortex-agent-project/SKILL.md"
REQ = ROOT / "requirements/REQ-012_guided_cortex_code_adoption_skill.md"


def _skill_parts() -> tuple[dict, str]:
    text = SKILL.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", text, flags=re.DOTALL)
    assert match is not None
    return yaml.safe_load(match.group(1)), match.group(2)


def _fenced_bash_commands(text: str) -> list[list[str]]:
    commands: list[list[str]] = []
    for block in re.findall(r"```bash\n(.*?)\n```", text, flags=re.DOTALL):
        logical = block.replace("\\\n", " ")
        for line in logical.splitlines():
            line = line.strip()
            if line.startswith("dbt-cortex-agent "):
                commands.append(shlex.split(line)[1:])
    return commands


def _all_fenced_shell_commands(text: str) -> list[list[str]]:
    commands: list[list[str]] = []
    for block in re.findall(r"```bash\n(.*?)\n```", text, flags=re.DOTALL):
        logical = block.replace("\\\n", " ")
        for line in logical.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                commands.append(shlex.split(line))
    return commands


def _selects(description: str, prompt: str) -> bool:
    trigger_text = description.split("Triggers:", 1)[1]
    triggers = [item.strip().lower().rstrip(".") for item in trigger_text.split(",")]
    normalized = " ".join(prompt.lower().split())
    return any(trigger in normalized for trigger in triggers)


def test_canonical_project_skill_is_single_file_script_free_and_bounded() -> None:
    files = sorted(path.relative_to(SKILL_ROOT).as_posix() for path in SKILL_ROOT.rglob("*") if path.is_file())
    assert files == ["dbt-cortex-agent-project/SKILL.md"]
    assert len(SKILL.read_text(encoding="utf-8").splitlines()) < 500
    assert not list(SKILL_ROOT.rglob("*.py"))
    assert not list(SKILL_ROOT.rglob("*.sh"))

    frontmatter, body = _skill_parts()
    assert frontmatter["name"] == "dbt-cortex-agent-project"
    assert "dbt_cortex_agent 0.3.1" in frontmatter["description"]
    for heading in ("## Workflow", "## Stopping points", "## Output"):
        assert heading in body


def test_skill_covers_drivetrain_routes_authority_and_manual_parity() -> None:
    _, body = _skill_parts()
    required = (
        "Discover the project read-only",
        "Objective:",
        "Levers:",
        "Data:",
        "Proof:",
        "Assembly line:",
        "Existing semantic view",
        "Fixed Orders starter",
        "Existing Agent migration",
        "Optional evaluation authoring",
        "manual command parity",
        "dbt Core with `dbt-snowflake` is authoritative",
        "Fusion/fdbt may provide advisory feedback",
        "Cortex Code file tools",
    )
    assert all(phrase in body for phrase in required)


def test_skill_commands_parse_with_the_shipped_parser() -> None:
    _, body = _skill_parts()
    commands = _fenced_bash_commands(body)
    assert commands
    parser = build_parser()
    for command in commands:
        try:
            parser.parse_args(command)
        except SystemExit as exc:
            pytest.fail(f"skill command does not parse ({exc.code}): {shlex.join(command)}")


def test_every_fenced_shell_command_has_a_known_parser_authority() -> None:
    _, body = _skill_parts()
    commands = _all_fenced_shell_commands(body)
    assert commands
    assert all(command[0] in {"dbt", "dbt-cortex-agent"} for command in commands)
    assert sum(command[0] == "dbt-cortex-agent" for command in commands) == len(
        _fenced_bash_commands(body)
    )


def test_fenced_dbt_commands_parse_when_dbt_core_is_installed() -> None:
    dbt = shutil.which("dbt")
    if dbt is None:
        pytest.skip("dbt Core is verified separately by the compatibility matrix")
    _, body = _skill_parts()
    commands = [command for command in _all_fenced_shell_commands(body) if command[0] == "dbt"]
    assert commands
    for command in commands:
        completed = subprocess.run(
            [dbt, *command[1:], "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, shlex.join(command)


def test_skill_has_no_parse_bypass_fixed_environment_or_lifecycle_copy() -> None:
    text = SKILL.read_text(encoding="utf-8")
    lowered = text.lower()
    forbidden = (
        "--no-parse",
        "analytics_dev",
        "am_ski_resort_dbt_focus",
        "dbt_focus",
        "connection sandbox",
        "target sandbox",
        "create agent",
        "alter agent",
        "drop agent",
        "run_eval.py",
    )
    assert all(value not in lowered for value in forbidden)
    assert "<TARGET>" in text
    assert "<DATABASE>" in text
    assert "<CONNECTION>" in text
    assert "do not create wrapper scripts" in lowered
    assert "https://example.invalid" not in lowered
    assert not re.search(r"\b[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*\b", text)


def test_skill_uses_one_agent_and_optional_eval_without_projection_deploy() -> None:
    _, body = _skill_parts()
    lowered = body.lower()
    assert "an agent\ncan be authored, rendered, deployed, and smoked without an eval model" in lowered
    assert "never create, deploy, clone, or suffix a\nsecond agent" in lowered
    assert "never\npropose a second agent deployment" in lowered
    assert "--projection" not in body
    assert "native_eval" not in body
    assert body.count("dbt-cortex-agent agent deploy") == 2


def test_skill_has_independent_ordered_approval_stops() -> None:
    _, body = _skill_parts()
    stops = (
        "## STOP 1 — local project writes",
        "## STOP 2 — Snowflake mutation or runtime",
        "## STOP 3 — paid evaluation",
        "## STOP 4 — baseline movement",
    )
    positions = [body.index(stop) for stop in stops]
    assert positions == sorted(positions)
    assert "Preview is evidence, not approval" in body
    assert "Never combine or infer approvals" in body
    assert body.count("explicitly approves") >= 4
    assert body.count("boundary packet containing the objective") == 4
    resume_conditions = (
        "Resume only for the approved local file plan.",
        "Resume only for the approved command.",
        "Resume only for the approved run.",
        "Resume only for the approved one-movement command.",
    )
    assert all(condition in body for condition in resume_conditions)


@pytest.mark.parametrize(
    "prompt",
    [
        "Help me adopt dbt cortex agent in our analytics project",
        "Add cortex agent to dbt using our semantic view",
        "Migrate cortex agent to dbt and preserve its tools",
        "Author dbt agent evaluation ground truth for our existing exposure",
        "Guide this dbt agent project from objective to proof",
        "Set up the orders agent starter in my existing project",
        "Use the orders agent starter in a new dbt project",
    ],
)
def test_positive_trigger_corpus_selects_skill(prompt: str) -> None:
    frontmatter, _ = _skill_parts()
    assert _selects(frontmatter["description"], prompt)


@pytest.mark.parametrize(
    "prompt",
    [
        "Explain what Cortex Agents are",
        "Fix a failing dbt model test",
        "Render this existing Agent specification",
        "How do semantic views work?",
        "Run an evaluation gate on this candidate artifact",
        "Author a Cortex Agent evaluation outside dbt",
    ],
)
def test_near_miss_trigger_corpus_does_not_select_skill(prompt: str) -> None:
    frontmatter, _ = _skill_parts()
    assert not _selects(frontmatter["description"], prompt)


@pytest.mark.parametrize(
    "prompt",
    [
        "Create a Streamlit dashboard",
        "Summarize this PDF",
        "Optimize my warehouse costs",
        "List files in this directory",
    ],
)
def test_negative_trigger_corpus_does_not_select_skill(prompt: str) -> None:
    frontmatter, _ = _skill_parts()
    assert not _selects(frontmatter["description"], prompt)


def test_req_012_and_adopter_surfaces_document_skill_contract() -> None:
    requirement = REQ.read_text(encoding="utf-8").lower()
    for heading in (
        "## summary",
        "## business context",
        "## objective",
        "## acceptance criteria",
        "## user stories",
        "## dependencies",
        "## out of scope",
        "## notes",
    ):
        assert heading in requirement

    surfaces = {
        "README.md": ROOT / "README.md",
        "first-agent": ROOT / "docs/getting-started/first-agent.md",
        "compatibility": ROOT / "docs/reference/compatibility.md",
        "changelog": ROOT / "CHANGELOG.md",
    }
    for name, path in surfaces.items():
        text = path.read_text(encoding="utf-8").lower()
        assert "script-free" in text, name
        assert "0.3.1" in text, name
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in surfaces.values())
    assert "not published" in combined or "not a claim of\ncatalog publication" in combined
    assert "live snowflake verification" in combined or "live-verification claim" in combined


@pytest.mark.parametrize(
    ("scenario", "route", "required_outputs", "first_stop"),
    [
        (
            "new project Orders starter",
            "#### B. Fixed Orders starter",
            ("--starter orders", "exact local paths and changes", "parse/validate/render"),
            "## STOP 1 — local project writes",
        ),
        (
            "existing semantic view",
            "#### A. Existing semantic view",
            ("semantic_view_model", "depends_on", "Cortex Code file tools"),
            "## STOP 1 — local project writes",
        ),
        (
            "existing Agent migration",
            "#### C. Existing Agent migration",
            ("migration table", "Preserve the existing live Agent", "agent render"),
            "## STOP 1 — local project writes",
        ),
        (
            "eval authoring",
            "#### D. Optional evaluation authoring",
            ("ground_truth_output", "ground_truth_invocations", "eval run"),
            "## STOP 1 — local project writes",
        ),
    ],
)
def test_guided_transcript_routes_produce_expected_output_and_stop_before_writes(
    scenario: str,
    route: str,
    required_outputs: tuple[str, ...],
    first_stop: str,
) -> None:
    _, body = _skill_parts()
    route_position = body.index(route)
    stop_position = body.index(first_stop)
    assert route_position < stop_position, scenario
    assert all(output in body for output in required_outputs), scenario
    assert "Do not create, edit, generate, install dependencies, or apply starter files" in body
    assert body.index("## STOP 2 — Snowflake mutation or runtime") > stop_position
    assert body.index("## STOP 3 — paid evaluation") > stop_position
    assert body.index("## STOP 4 — baseline movement") > stop_position
