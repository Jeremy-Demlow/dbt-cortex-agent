from __future__ import annotations

import argparse

from ..config import Config
from ..eval.baseline import accept_baseline
from ..eval.compare import compare_results
from ..eval.gate import gate_candidate
from ..eval.lifecycle import build_plan, run_evaluation
from ..eval.results import load_result
from .common import add_allowlists, emit_json, require_explicit_connection


def register(subparsers: argparse._SubParsersAction, shared: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "eval",
        help="run and gate manifest-owned evaluations",
        description="Plan evaluations locally, opt into paid runs, and manage local comparison evidence.",
        epilog=(
            "Examples:\n"
            "  dbt-cortex-agent eval run --agent orders_assistant --suite core --json\n"
            "  dbt-cortex-agent eval gate candidate.json --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="eval_command", required=True)
    run = commands.add_parser("run", parents=[shared], help="plan or execute evaluation [PAID with --apply]")
    run.add_argument("--agent", required=True, help="logical Agent name")
    run.add_argument("--suite", required=True, help="evaluation suite name")
    run.add_argument("--run-name", help="explicit evaluation run name")
    run.add_argument("--poll-attempts", type=int, default=60, help="maximum status polls (default: 60)")
    run.add_argument("--poll-interval", type=float, default=30, help="seconds between polls (default: 30)")
    run.add_argument("--transient-retries", type=int, default=1, help="retries for transient failures (default: 1)")
    add_allowlists(run)
    run.add_argument("--apply", action="store_true", help="[PAID] start evaluation; default only renders the plan")
    run.set_defaults(handler=handle)

    compare = commands.add_parser("compare", parents=[shared], help="compare baseline and candidate artifacts")
    compare.add_argument("baseline")
    compare.add_argument("candidate")
    compare.add_argument("--tolerance", type=float, default=0.01)
    compare.set_defaults(handler=handle)

    accept = commands.add_parser("accept-baseline", parents=[shared], help="preview or accept a passing baseline [MUTATION with --apply]")
    accept.add_argument("candidate")
    accept.add_argument("--baseline-dir")
    accept.add_argument("--apply", action="store_true", help="[MUTATION] write the baseline; default is preview")
    accept.add_argument("--force", action="store_true", help="overwrite an existing baseline when applying")
    accept.set_defaults(handler=handle)

    gate = commands.add_parser("gate", parents=[shared], help="gate a candidate against thresholds and baseline")
    gate.add_argument("candidate")
    gate.add_argument("--baseline")
    gate.add_argument("--baseline-dir")
    gate.add_argument("--tolerance", type=float, default=0.01)
    gate.set_defaults(handler=handle)


def handle(args: argparse.Namespace, config: Config) -> int:
    if args.eval_command == "run":
        if args.apply:
            require_explicit_connection(config, "Evaluation apply")
        plan = build_plan(
            config,
            agent_name=args.agent,
            suite_name=args.suite,
            parse=not args.no_parse,
        )
        plan_payload = {
            "agent": plan.agent_name,
            "suite": plan.suite_name,
            "agent_object": plan.agent_fqn,
            "eval_model": plan.eval_model,
            "dataset": plan.table_fqn,
            "stage": plan.stage_fqn,
            "target_role": plan.target_role,
            "metrics": plan.metric_names,
            "plan_identity": plan.plan_identity,
            "suite_signature": plan.suite_signature,
            "paid_apply": bool(args.apply),
        }
        output = run_evaluation(
            config,
            plan,
            apply=args.apply,
            run_name=args.run_name,
            poll_attempts=args.poll_attempts,
            poll_interval=args.poll_interval,
            transient_retries=args.transient_retries,
            allowed_targets=args.allow_target,
            allowed_databases=args.allow_database,
        )
        candidate = load_result(output) if output else None
        payload = {"command": "eval run", "plan": plan_payload, "candidate": str(output) if output else None, "passed": candidate.get("passed") if candidate else None}
        if args.json:
            emit_json(payload)
        else:
            emit_json(plan_payload)
            if output:
                print(f"Candidate: {output}")
        return 0 if candidate is None or candidate.get("passed") else 1
    if args.eval_command == "compare":
        result = compare_results(load_result(args.baseline), load_result(args.candidate), args.tolerance)
        emit_json(result)
        return 0 if result["passed"] else 1
    if args.eval_command == "accept-baseline":
        directory = args.baseline_dir or str(config.artifact_dir / "baselines")
        candidate = load_result(args.candidate)
        if args.force and not args.apply:
            raise ValueError("--force requires --apply")
        target = (
            accept_baseline(candidate, directory, force=args.force)
            if args.apply
            else None
        )
        if args.json:
            emit_json(
                {
                    "command": "eval accept-baseline",
                    "applied": bool(args.apply),
                    "agent": candidate["agent"],
                    "suite": candidate["suite"],
                    "baseline": str(target) if target else None,
                    "baseline_dir": directory,
                }
            )
        elif not args.apply:
            print(
                f"[DRY RUN] would accept baseline for "
                f"{candidate['agent']}/{candidate['suite']} in {directory}"
            )
        else:
            print(f"Baseline: {target}")
        return 0
    directory = args.baseline_dir or str(config.artifact_dir / "baselines")
    result = gate_candidate(
        args.candidate,
        baseline=args.baseline,
        baseline_dir=directory,
        default_tolerance=args.tolerance,
    )
    emit_json(result)
    return 0 if result["passed"] else 1