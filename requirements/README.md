# Requirements index

Requirements are the product contract. A requirement is complete only when its acceptance criteria
have reproducible verification evidence. Historical version-specific requirements remain indexed as
provenance. The current release target is `0.0.8`; REQ-021 through REQ-028 remain
the qualified `0.0.6` foundation, extended by the current corrective release.

| Requirement | Scope | Status |
|---|---|---|
| [REQ-002](REQ-002_v030_identity_and_python_ownership.md) | Combined dbt/Python identity and ownership boundary | Complete (v0.3.0 foundation) |
| [REQ-003](REQ-003_explicit_bootstrap_configuration.md) | Explicit bootstrap configuration | Complete |
| [REQ-004](REQ-004_lifecycle_safety.md) | Lifecycle and safety hardening | Complete |
| [REQ-005](REQ-005_dbt_rendered_eval_plan.md) | dbt-rendered evaluation plan | Complete |
| [REQ-006](REQ-006_stable_cli.md) | Stable domain-oriented CLI | Complete |
| [REQ-007](REQ-007_adopter_documentation.md) | Complete adopter documentation | Complete (v0.3.0 foundation, extended by REQ-011/012) |
| [REQ-008](REQ-008_standalone_ci.md) | Standalone package verification | Complete |
| [REQ-009](REQ-009_simple_maintainer_policy.md) | Simple maintainer-led policy | Complete |
| [REQ-010](REQ-010_trusted_pypi_publishing.md) | Trusted PyPI publishing path | Complete (automation only; no publication performed) |
| [REQ-011](REQ-011_tutorial_product_readiness.md) | Historical Orders starter, projection render/deploy, and Agent smoke contract | Complete historical record; projection topology superseded by REQ-013 |
| [REQ-012](REQ-012_guided_cortex_code_adoption_skill.md) | Guided Cortex Code adoption and immutable-SHA doctor | Complete (v0.3.1) |
| [REQ-013](REQ-013_single_physical_agent_evaluation.md) | One physical Agent per enabled exposure and target, with optional same-Agent evaluations | Complete |
| [REQ-014](REQ-014_installed_wheel_single_agent_verifier.md) | Installed-wheel Agent-only and optional-eval end-to-end verification | Complete |
| [REQ-015](REQ-015_authoritative_snow_dbt_execution_context.md) | Authoritative Snow CLI connection context for dbt, Snow CLI, and runtime operations | Complete |
| [REQ-016](REQ-016_agent_monitor_access_contract.md) | Agent USAGE and MONITOR grant lifecycle for runtime and evaluation roles | In progress |
| [REQ-017](REQ-017_tool_dependency_access_contract.md) | Least-privilege access contract for Agent tool dependencies | In progress |
| [REQ-018](REQ-018_sanitized_evaluation_failure_diagnostics.md) | Whitelist-only terminal evaluation diagnostics | Complete |
| [REQ-019](REQ-019_resource_scoped_multi_database_context.md) | Resource-scoped multi-database Agent context | Complete (v0.0.3) |
| [REQ-020](REQ-020_package_native_workflows.md) | Package-native deploy and evaluation-verification workflows | Complete (v0.0.5) |
| [REQ-021](REQ-021_python_design_and_maintainability.md) | Python design, maintainability, and quality gates | Complete (v0.0.6) |
| [REQ-022](REQ-022_package_native_workflow_safety.md) | Package-native workflow safety and proof | Complete (v0.0.6) |
| [REQ-023](REQ-023_macro_api_and_reconciliation.md) | dbt macro API, safety, and restartable reconciliation | Complete (v0.0.6) |
| [REQ-024](REQ-024_agent_scaffold_and_developer_journey.md) | Generic Agent scaffold and developer journey | Complete (v0.0.6) |
| [REQ-025](REQ-025_agent_version_promotion_and_rollback.md) | Immutable version promotion, rollback, and recovery | Complete (v0.0.6) |
| [REQ-026](REQ-026_guarded_agent_retirement.md) | Explicit, guarded Agent retirement | Complete (v0.0.6) |
| [REQ-027](REQ-027_agent_runtime_protocol_and_output.md) | Agent streaming protocol and compact output | Complete (v0.0.6) |
| [REQ-028](REQ-028_executable_developer_ci_guide.md) | Executable developer and CI/CD guide | Complete (v0.0.6) |
| [REQ-029](REQ-029_macro_eval_execution_safety.md) | Executable and injection-safe dbt evaluation macros | Complete (v0.0.7) |
| [REQ-030](REQ-030_runtime_failure_evidence.md) | Runtime assertion evidence and honest exception classification | Complete (v0.0.7) |
| [REQ-031](REQ-031_shared_controlled_failure_contract.md) | Shared controlled-operation classification and routing inspection | Complete (v0.0.8) |

See [user stories](user_stories.md), [test cases](../tests/test_cases.md), and
[regression coverage](../tests/regression.md) for the linked behavioral evidence.