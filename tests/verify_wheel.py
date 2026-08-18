from pathlib import Path
import sys
from zipfile import ZipFile


EXPECTED_PACKAGE_FILES = {
    "dbt_cortex_agent/__init__.py",
    "dbt_cortex_agent/artifacts.py",
    "dbt_cortex_agent/cli.py",
    "dbt_cortex_agent/commands/__init__.py",
    "dbt_cortex_agent/commands/agent.py",
    "dbt_cortex_agent/commands/bootstrap.py",
    "dbt_cortex_agent/commands/common.py",
    "dbt_cortex_agent/commands/eval.py",
    "dbt_cortex_agent/commands/manifest.py",
    "dbt_cortex_agent/commands/skill.py",
    "dbt_cortex_agent/config.py",
    "dbt_cortex_agent/dbt_runner.py",
    "dbt_cortex_agent/doctor.py",
    "dbt_cortex_agent/execution_context.py",
    "dbt_cortex_agent/eval/__init__.py",
    "dbt_cortex_agent/eval/baseline.py",
    "dbt_cortex_agent/eval/compare.py",
    "dbt_cortex_agent/eval/dataset.py",
    "dbt_cortex_agent/eval/gate.py",
    "dbt_cortex_agent/eval/lifecycle.py",
    "dbt_cortex_agent/eval/results.py",
    "dbt_cortex_agent/identifiers.py",
    "dbt_cortex_agent/init.py",
    "dbt_cortex_agent/invoke.py",
    "dbt_cortex_agent/manifest.py",
    "dbt_cortex_agent/skills.py",
    "dbt_cortex_agent/snow.py",
    "dbt_cortex_agent/starters/orders/models/agents/orders_assistant/agent.yml",
    "dbt_cortex_agent/starters/orders/models/agents/orders_assistant/orders_assistant.sql",
    "dbt_cortex_agent/starters/orders/models/agents/orders_assistant/evals/core.yml",
    "dbt_cortex_agent/starters/orders/models/agents/orders_assistant/evals/orders_assistant_core.sql",
    "dbt_cortex_agent/starters/orders/models/semantic/sem_orders.sql",
    "dbt_cortex_agent/starters/orders/seeds/orders.csv",
    "dbt_cortex_agent/starters/orders/seeds/orders.yml",
}


def main(path: str) -> int:
    wheel = Path(path)
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
    package_files = {name for name in names if name.startswith("dbt_cortex_agent/")}
    if package_files != EXPECTED_PACKAGE_FILES:
        missing = sorted(EXPECTED_PACKAGE_FILES - package_files)
        unexpected = sorted(package_files - EXPECTED_PACKAGE_FILES)
        raise SystemExit(f"wheel inventory mismatch: missing={missing}, unexpected={unexpected}")
    if not any(name.endswith(".dist-info/entry_points.txt") for name in names):
        raise SystemExit("wheel is missing console-script metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))