from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import Config
from ..dbt_runner import CommandRunner, run_dbt_build
from ..domain import is_controlled_operation_error
from .compare import compare_results
from .gate import baseline_path
from .lifecycle import EvalPlan, build_plan, run_evaluation, validate_evaluation_apply
from .results import eligibility_failures, load_result


@dataclass(frozen=True)
class VerifySelection:
    plan: EvalPlan
    baseline: Path


def _bind_candidate(candidate: dict[str, Any], plan: EvalPlan) -> None:
    expected = {
        "plan_schema_version": plan.schema_version,
        "plan_identity": plan.plan_identity,
        "suite_signature": plan.suite_signature,
        "agent": plan.agent_name,
        "suite": plan.suite_name,
        "eval_model": plan.eval_model,
        "agent_fqn": plan.agent_fqn,
        "dataset_fqn": plan.table_fqn,
        "stage_fqn": plan.stage_fqn,
        "ordered_ground_truth_refs": plan.ordered_ground_truth_refs,
        "metric_names": plan.metric_names,
        "thresholds": plan.thresholds,
        "regression_tolerances": plan.regression_tolerances,
    }
    mismatched = [field for field, value in expected.items() if candidate.get(field) != value]
    if mismatched:
        raise ValueError(
            "Evaluation candidate does not match current plan: " + ", ".join(mismatched)
        )


def build_verify_selections(
    config: Config,
    agent_name: str,
    suite_names: list[str],
    baseline_dir: str | Path,
    *,
    parse: bool,
) -> tuple[VerifySelection, ...]:
    if not suite_names or any(not value.strip() for value in suite_names):
        raise ValueError("eval verify requires at least one nonblank --suite")
    if len(set(suite_names)) != len(suite_names):
        raise ValueError("eval verify suite selections must be unique")
    selections = []
    for index, suite in enumerate(suite_names):
        plan = build_plan(
            config,
            agent_name=agent_name,
            suite_name=suite,
            parse=parse and index == 0,
        )
        baseline = baseline_path(
            baseline_dir,
            {
                "plan_identity": {"target_name": plan.target_name},
                "agent_fqn": plan.agent_fqn,
                "suite": suite,
            },
        )
        selections.append(VerifySelection(plan=plan, baseline=baseline))
    return tuple(sorted(selections, key=lambda item: (item.plan.agent_fqn, item.plan.suite_name)))


def verify_evaluations(
    config: Config,
    selections: tuple[VerifySelection, ...],
    *,
    apply: bool,
    allowed_targets: list[str],
    allowed_databases: list[str],
    poll_attempts: int,
    poll_interval: float,
    transient_retries: int,
    runner: CommandRunner | None = None,
    evaluate: Callable[..., Path | None] = run_evaluation,
    render_plan: Callable[..., EvalPlan] = build_plan,
) -> dict[str, Any]:
    planned: list[dict[str, Any]] = [
        {
            "agent": item.plan.agent_name,
            "suite": item.plan.suite_name,
            "agent_fqn": item.plan.agent_fqn,
            "eval_model": item.plan.eval_model,
            "baseline": str(item.baseline),
            "baseline_state": "established" if item.baseline.is_file() else "not_established",
        }
        for item in selections
    ]
    if not apply:
        return {
            "command": "eval verify",
            "applied": False,
            "passed": None,
            "outcome": "planned",
            "suites": planned,
        }

    validate_evaluation_apply(
        config,
        [item.plan for item in selections],
        allowed_targets=allowed_targets,
        allowed_databases=allowed_databases,
        poll_attempts=poll_attempts,
        poll_interval=poll_interval,
        transient_retries=transient_retries,
    )

    command_runner = runner or CommandRunner()
    results: list[dict[str, Any]] = []
    quality_failed = False
    for selection_index, (item, plan_payload) in enumerate(zip(selections, planned, strict=True)):
        plan = item.plan
        candidate_path = None
        execution = "failed"
        gate_state = "not_run"
        try:
            build = run_dbt_build(
                config.dbt_executable,
                config.project_dir,
                config.target,
                [plan.eval_model],
                command_runner,
                config.dbt_env,
            )
            if build.returncode != 0:
                raise RuntimeError(
                    build.stderr.strip() or build.stdout.strip() or "eval model build failed"
                )
            current_plan = render_plan(
                config,
                agent_name=plan.agent_name,
                suite_name=plan.suite_name,
                parse=True,
                runner=command_runner,
            )
            if (
                current_plan.suite_signature != plan.suite_signature
                or current_plan.plan_identity != plan.plan_identity
            ):
                raise RuntimeError(
                    f"Evaluation plan changed while materializing {plan.eval_model}; "
                    "retry from preview"
                )
            candidate_path = evaluate(
                config,
                current_plan,
                apply=True,
                poll_attempts=poll_attempts,
                poll_interval=poll_interval,
                transient_retries=transient_retries,
                allowed_targets=allowed_targets,
                allowed_databases=allowed_databases,
            )
            if candidate_path is None:
                raise RuntimeError("Applied evaluation produced no candidate")
            execution = "completed"
            gate_state = "error"
            candidate = load_result(candidate_path, "candidate")
            _bind_candidate(candidate, current_plan)
            if item.baseline.is_file():
                gate = compare_results(load_result(item.baseline, "baseline"), candidate)
                passed = bool(gate["passed"])
            else:
                passed = not eligibility_failures(candidate)
        except Exception as exc:
            if not is_controlled_operation_error(exc):
                raise
            results.append(
                {
                    **plan_payload,
                    "candidate": str(candidate_path) if candidate_path is not None else None,
                    "execution": execution,
                    "gate": gate_state,
                    "passed": None,
                    "error": str(exc),
                }
            )
            results.extend(
                {
                    **remaining_payload,
                    "candidate": None,
                    "execution": "not_run",
                    "gate": "not_run",
                    "passed": None,
                    "error": None,
                }
                for remaining_payload in planned[selection_index + 1 :]
            )
            return {
                "command": "eval verify",
                "applied": True,
                "passed": None,
                "quality_passed": not quality_failed,
                "outcome": "infrastructure_failed",
                "error": str(exc),
                "suites": results,
            }
        quality_failed = quality_failed or not passed
        results.append(
            {
                **plan_payload,
                "candidate": str(candidate_path),
                "execution": "completed",
                "gate": "passed" if passed else "failed",
                "passed": passed,
            }
        )
    return {
        "command": "eval verify",
        "applied": True,
        "passed": not quality_failed,
        "quality_passed": not quality_failed,
        "outcome": "quality_failed" if quality_failed else "passed",
        "suites": results,
    }
