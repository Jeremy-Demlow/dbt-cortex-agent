from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

import yaml
from jinja2 import Environment, StrictUndefined


AGENT = "orders_assistant"
SUITE = "core"
TARGET = "sandbox"
DATABASE = "WHEEL_VERIFY_DB"
EVAL_FILES = (
    Path("models/agents/orders_assistant/evals/core.yml"),
    Path("models/agents/orders_assistant/evals/orders_assistant_core.sql"),
)
FORBIDDEN_ARGUMENTS = {"--connection", "accept-baseline"}
FORBIDDEN_COMMANDS = {"snow", "snow.exe"}


@dataclass(frozen=True)
class ProjectEvidence:
    name: str
    project_dir: Path
    doctor: dict[str, Any]
    manifest: dict[str, Any]
    compiled_agent: dict[str, Any]
    smoke: dict[str, Any]
    eval_plan: dict[str, Any] | None
    eval_log: str
    render_digest_before_eval: str
    render_digest_after_eval: str


def run_checked(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    executable = Path(command[0]).name.lower()
    if executable in FORBIDDEN_COMMANDS:
        raise ValueError(f"unsafe verifier command: {' '.join(command)}")
    if any(argument in FORBIDDEN_ARGUMENTS for argument in command):
        raise ValueError(f"unsafe verifier command: {' '.join(command)}")
    if "--apply" in command and not (
        len(command) > 1 and Path(command[0]).name.startswith("dbt-cortex-agent") and command[1] == "init"
    ):
        raise ValueError(f"unsafe verifier command: {' '.join(command)}")
    result = subprocess.run(
        list(command), cwd=cwd, env=env, text=True, capture_output=True, check=False
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result


def run_expected_failure(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    expected: str,
) -> None:
    if "--apply" in command or any(
        argument in FORBIDDEN_ARGUMENTS for argument in command
    ):
        raise ValueError(f"unsafe verifier command: {' '.join(command)}")
    result = subprocess.run(
        list(command), cwd=cwd, env=env, text=True, capture_output=True, check=False
    )
    detail = "\n".join((result.stdout, result.stderr))
    if result.returncode == 0 or expected not in detail:
        raise AssertionError(
            f"command did not fail with expected guidance: {' '.join(command)}\n{detail.strip()}"
        )


def parse_json_output(result: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} did not emit one JSON document: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON must be an object")
    return payload


def contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(contains_key(item, key) for item in value)
    return False


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_consumer_project(project_dir: Path, package_dir: Path, *, include_eval: bool) -> None:
    project_dir.mkdir(parents=True)
    (project_dir / "dbt_project.yml").write_text(
        """name: wheel_verify_consumer
version: 1.0.0
config-version: 2
profile: wheel_verify_consumer
model-paths: [models]
seed-paths: [seeds]
vars:
  cortex_agent_deploy_target: sandbox
  cortex_agent_allowed_targets: [sandbox]
  cortex_agent_allowed_databases: [WHEEL_VERIFY_DB]
  cortex_agent_schema: AGENTS
  cortex_eval_schema: EVAL
models:
  wheel_verify_consumer:
    semantic:
      +materialized: semantic_view
      +schema: semantic
""",
        encoding="utf-8",
    )
    (project_dir / "profiles.yml").write_text(
        """wheel_verify_consumer:
  target: sandbox
  outputs:
    sandbox:
      type: snowflake
      account: offline
      user: offline
      password: offline
      role: OFFLINE_ROLE
      warehouse: OFFLINE_WAREHOUSE
      database: WHEEL_VERIFY_DB
      schema: ANALYTICS
      threads: 1
""",
        encoding="utf-8",
    )
    relative_package = os.path.relpath(package_dir, project_dir)
    (project_dir / "packages.yml").write_text(
        "packages:\n"
        f"  - local: {relative_package}\n"
        "  - package: Snowflake-Labs/dbt_semantic_view\n"
        "    version: 1.0.5\n",
        encoding="utf-8",
    )
    if not include_eval:
        for relative_path in EVAL_FILES:
            target = project_dir / relative_path
            if target.exists():
                target.unlink()


def compiled_agent_evidence(project_dir: Path) -> tuple[dict[str, Any], str]:
    manifest = json.loads((project_dir / "target/manifest.json").read_text(encoding="utf-8"))
    nodes = [
        node
        for node in manifest.get("nodes", {}).values()
        if node.get("resource_type") == "model" and node.get("name") == AGENT
    ]
    if len(nodes) != 1:
        raise AssertionError(f"expected one compiled {AGENT} model, found {len(nodes)}")
    node = nodes[0]
    raw_code = node.get("raw_code")
    if not isinstance(raw_code, str):
        raise AssertionError(f"parsed {AGENT} model has no raw_code")
    rendered = Environment(
        extensions=["jinja2.ext.do"], undefined=StrictUndefined
    ).from_string(raw_code).render(
        config=lambda **_kwargs: "",
        ref=lambda *_args, **_kwargs: "",
        env_var=lambda _name, default=None: default,
        target=SimpleNamespace(
            database=DATABASE,
            warehouse="OFFLINE_WAREHOUSE",
            name=TARGET,
        ),
    )
    spec = yaml.safe_load(rendered)
    if not isinstance(spec, dict):
        raise AssertionError(f"compiled {AGENT} model body is not a mapping")
    alias = node.get("alias") or node.get("name")
    return (
        {
            "agent": AGENT,
            "physical_agent": ".".join((node["database"], node["schema"], alias)),
            "lifecycle_contract": "single_agent",
            "target": TARGET,
            "spec": spec,
        },
        hashlib.sha256(
            json.dumps(spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    )


def validate_project_evidence(evidence: ProjectEvidence, *, include_eval: bool) -> str:
    if not evidence.doctor.get("passed"):
        raise AssertionError(f"{evidence.name}: doctor failed")
    diagnostics = {
        item["name"]: item for item in evidence.doctor.get("diagnostics", [])
    }
    expected_evals = "orders_assistant_core" if include_eval else "none"
    if diagnostics.get("enabled evals", {}).get("detail") != expected_evals:
        raise AssertionError(f"{evidence.name}: expected enabled evals {expected_evals!r}")
    if evidence.manifest.get("agents") != [AGENT]:
        raise AssertionError(f"{evidence.name}: manifest did not select exactly {AGENT}")

    fqn = evidence.compiled_agent.get("physical_agent")
    if not isinstance(fqn, str):
        raise AssertionError(f"{evidence.name}: compiled model has no physical Agent FQN")
    smoke_object = evidence.smoke.get("agent_object")
    if not isinstance(smoke_object, str) or fqn.split(".")[-1] != smoke_object:
        raise AssertionError(f"{evidence.name}: smoke Agent FQN drift")
    if "_EVAL" in fqn.upper():
        raise AssertionError(f"{evidence.name}: evaluation-specific physical Agent identity")
    for label, payload in (("compiled", evidence.compiled_agent), ("smoke", evidence.smoke)):
        if contains_key(payload, "projection"):
            raise AssertionError(f"{evidence.name}: {label} contains projection metadata")
    if evidence.smoke.get("applied") is not False:
        raise AssertionError(f"{evidence.name}: preview unexpectedly applied")
    if evidence.smoke.get("response") is not None or evidence.smoke.get("passed") is not None:
        raise AssertionError(f"{evidence.name}: smoke preview invoked runtime")

    if include_eval:
        if evidence.eval_plan is None:
            raise AssertionError(f"{evidence.name}: missing optional eval plan")
        if evidence.eval_plan.get("candidate") is not None:
            raise AssertionError(f"{evidence.name}: eval preview produced a candidate")
        plan = evidence.eval_plan.get("plan", {})
        if plan.get("paid_apply") is not False or plan.get("agent_object") != fqn:
            raise AssertionError(f"{evidence.name}: eval plan identity or paid boundary mismatch")
        if contains_key(evidence.eval_plan, "projection"):
            raise AssertionError(f"{evidence.name}: eval plan contains projection metadata")
        if "dbt_cortex_agent.cortex_eval__execution_plan" not in evidence.eval_log:
            raise AssertionError(
                f"{evidence.name}: package-qualified eval plan macro was not observed"
            )
        forbidden_macros = ("cortex_agent__deploy", "cortex_agent__render_spec")
        if any(macro in evidence.eval_log for macro in forbidden_macros):
            raise AssertionError(f"{evidence.name}: eval preview invoked Agent lifecycle macro")
        if evidence.render_digest_before_eval != evidence.render_digest_after_eval:
            raise AssertionError(f"{evidence.name}: eval preview changed the render artifact")
    elif evidence.eval_plan is not None or "cortex_eval__" in evidence.eval_log:
        raise AssertionError(f"{evidence.name}: Agent-only path performed an eval action")
    return fqn


def validate_pair(agent_only: ProjectEvidence, optional_eval: ProjectEvidence) -> dict[str, Any]:
    agent_only_fqn = validate_project_evidence(agent_only, include_eval=False)
    optional_eval_fqn = validate_project_evidence(optional_eval, include_eval=True)
    if agent_only_fqn != optional_eval_fqn:
        raise AssertionError("isolated projects resolved different Agent FQNs")
    agent_only_spec = agent_only.compiled_agent["spec"]
    optional_eval_spec = optional_eval.compiled_agent["spec"]
    if agent_only_spec != optional_eval_spec:
        raise AssertionError("optional eval metadata changed the rendered Agent specification")
    return {
        "passed": True,
        "agent_fqn": agent_only_fqn,
        "projects": {
            "agent_only": {"enabled_evals": 0, "eval_action_required": False},
            "agent_plus_optional_eval": {
                "enabled_evals": 1,
                "eval_deployed_agent": False,
                "paid_apply": False,
            },
        },
    }


def _copy_dbt_package(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    shutil.copy2(source / "dbt_project.yml", destination / "dbt_project.yml")
    shutil.copytree(source / "macros", destination / "macros")


def _venv_paths(venv: Path) -> tuple[Path, Path, Path]:
    scripts = venv / ("Scripts" if os.name == "nt" else "bin")
    return scripts / ("python.exe" if os.name == "nt" else "python"), scripts / "dbt", scripts / "dbt-cortex-agent"


def _write_fake_snow(path: Path) -> None:
    path.write_text("#!/usr/bin/env python3\nprint('Snowflake CLI verifier stub 0')\n", encoding="utf-8")
    path.chmod(0o755)


def _cli_json(cli: Path, arguments: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    return parse_json_output(run_checked([str(cli), *arguments], cwd=cwd, env=env), "CLI")


def exercise_project(
    project_dir: Path,
    *,
    cli: Path,
    dbt: Path,
    fake_snow: Path,
    env: dict[str, str],
    include_eval: bool,
) -> ProjectEvidence:
    env = {**env, "DBT_PROFILES_DIR": str(project_dir)}
    common = ["--project-dir", str(project_dir), "--target", TARGET, "--json"]
    run_checked(
        [str(dbt), "deps", "--project-dir", str(project_dir), "--profiles-dir", str(project_dir)],
        cwd=project_dir,
        env=env,
    )
    run_checked(
        [str(dbt), "parse", "--project-dir", str(project_dir), "--profiles-dir", str(project_dir), "--no-partial-parse"],
        cwd=project_dir,
        env=env,
    )
    doctor = _cli_json(
        cli,
        ["doctor", *common, "--dbt-executable", str(dbt), "--snow-executable", str(fake_snow)],
        cwd=project_dir,
        env=env,
    )
    manifest = _cli_json(
        cli,
        ["manifest", "validate", *common, "--dbt-executable", str(dbt), "--agent", AGENT],
        cwd=project_dir,
        env=env,
    )
    compiled_agent, before = compiled_agent_evidence(project_dir)
    smoke = _cli_json(
        cli,
        [
            "agent",
            "smoke",
            *common,
            "--dbt-executable",
            str(dbt),
            "--agent",
            AGENT,
            "--question",
            "What was total order revenue?",
        ],
        cwd=project_dir,
        env=env,
    )
    eval_plan = None
    eval_log = ""
    if include_eval:
        log_dir = project_dir / "eval-plan-logs"
        eval_env = {**env, "DBT_LOG_PATH": str(log_dir)}
        eval_plan = _cli_json(
            cli,
            [
                "eval",
                "run",
                *common,
                "--dbt-executable",
                str(dbt),
                "--agent",
                AGENT,
                "--suite",
                SUITE,
            ],
            cwd=project_dir,
            env=eval_env,
        )
        log_file = log_dir / "dbt.log"
        eval_log = log_file.read_text(encoding="utf-8") if log_file.is_file() else ""
    compiled_after, after = compiled_agent_evidence(project_dir)
    if compiled_after["spec"] != compiled_agent["spec"]:
        raise AssertionError(f"{project_dir.name}: eval preview changed the parsed Agent spec")
    return ProjectEvidence(
        project_dir.name,
        project_dir,
        doctor,
        manifest,
        compiled_agent,
        smoke,
        eval_plan,
        eval_log,
        before,
        after,
    )


def verify(args: argparse.Namespace) -> dict[str, Any]:
    wheel = args.wheel.resolve()
    package_source = args.dbt_package_dir.resolve()
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise FileNotFoundError(f"wheel not found: {wheel}")
    if not (package_source / "dbt_project.yml").is_file():
        raise FileNotFoundError(f"dbt package not found: {package_source}")
    source_checkout = package_source
    workspace_context = (
        tempfile.TemporaryDirectory(prefix="dbt-cortex-agent-wheel-")
        if args.workspace is None
        else None
    )
    workspace = Path(workspace_context.name if workspace_context else args.workspace).resolve()
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        if workspace == source_checkout or source_checkout in workspace.parents:
            raise ValueError("workspace must be outside the source checkout")
        venv = workspace / "venv"
        run_checked([sys.executable, "-m", "venv", str(venv)], cwd=workspace, env=os.environ.copy())
        python, dbt, cli = _venv_paths(venv)
        run_checked(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                str(wheel),
                f"dbt-core{args.dbt_core}",
                f"dbt-snowflake=={args.dbt_snowflake}",
            ],
            cwd=workspace,
            env=os.environ.copy(),
        )
        imported = run_checked(
            [str(python), "-c", "import dbt_cortex_agent; print(dbt_cortex_agent.__file__)"],
            cwd=workspace,
            env=os.environ.copy(),
        ).stdout.strip()
        if str(source_checkout) in imported:
            raise AssertionError(f"installed CLI imported from source checkout: {imported}")

        package_copy = workspace / "dbt_cortex_agent"
        _copy_dbt_package(package_source, package_copy)
        fake_snow = workspace / "snow-stub"
        _write_fake_snow(fake_snow)
        env = os.environ.copy()
        evidence = []
        for name, include_eval in (("agent-only", False), ("agent-plus-eval", True)):
            project_dir = workspace / name
            create_consumer_project(project_dir, package_copy, include_eval=include_eval)
            _cli_json(
                cli,
                [
                    "init",
                    "--project-dir",
                    str(project_dir),
                    "--target",
                    TARGET,
                    "--starter",
                    "orders",
                    "--apply",
                    "--json",
                ],
                cwd=workspace,
                env=env,
            )
            if not include_eval:
                for relative_path in EVAL_FILES:
                    (project_dir / relative_path).unlink()
            evidence.append(
                exercise_project(
                    project_dir,
                    cli=cli,
                    dbt=dbt,
                    fake_snow=fake_snow,
                    env=env,
                    include_eval=include_eval,
                )
            )
        result = validate_pair(evidence[0], evidence[1])
        result.update(
            {
                "wheel": str(wheel),
                "dbt_core": args.dbt_core,
                "dbt_snowflake": args.dbt_snowflake,
                "workspace_isolated": True,
                "installed_module": imported,
            }
        )
        return result
    finally:
        if workspace_context is not None:
            workspace_context.cleanup()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify an installed wheel against two isolated dbt consumers.")
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--dbt-package-dir", type=Path, required=True)
    parser.add_argument("--dbt-core", default="~=1.11.0")
    parser.add_argument("--dbt-snowflake", default="1.11.4")
    parser.add_argument("--workspace", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    result = verify(build_parser().parse_args(argv))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())