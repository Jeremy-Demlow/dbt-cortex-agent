# Requirements index

Requirements are the product contract. A requirement is complete only when its acceptance criteria
have reproducible verification evidence. Historical version-specific requirements remain indexed as
provenance. The current release candidate is `0.0.9`, pending qualification and
publication; REQ-021 through REQ-028 remain
the historical `0.0.6` foundation, extended by the current corrective release.
Current proof scope and uncovered acceptance gaps are explicit in
[`tests/requirement_evidence.json`](../tests/requirement_evidence.json). Collected
node linkage is not a passing test result. Structural checks, local behavior,
historical live reports, and pending qualification are not interchangeable.

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
| [REQ-021](REQ-021_python_design_and_maintainability.md) | Python design, maintainability, and quality gates | In progress; current coverage/quality-gate proof gaps |
| [REQ-022](REQ-022_package_native_workflow_safety.md) | Package-native workflow safety and proof | In progress; tasks 2 and 4 locally verified, no current live qualification |
| [REQ-023](REQ-023_macro_api_and_reconciliation.md) | dbt macro API, safety, and restartable reconciliation | In progress; task 3 locally verified, broader reconciliation/live gaps |
| [REQ-024](REQ-024_agent_scaffold_and_developer_journey.md) | Generic Agent scaffold and developer journey | In progress; installed/experimental round-trip gaps |
| [REQ-025](REQ-025_agent_version_promotion_and_rollback.md) | Immutable version promotion, rollback, and recovery | In progress; routing gaps, historical live report only |
| [REQ-026](REQ-026_guarded_agent_retirement.md) | Explicit, guarded Agent retirement | In progress; task 3 locally verified, retained-dependency/live gaps |
| [REQ-027](REQ-027_agent_runtime_protocol_and_output.md) | Agent streaming protocol and compact output | In progress; protocol corpus/schema gaps |
| [REQ-028](REQ-028_executable_developer_ci_guide.md) | Executable developer and CI/CD guide | In progress; task 6 proof map and task 7 local contracts; current exact-install/live gaps |
| [REQ-029](REQ-029_macro_eval_execution_safety.md) | Executable and injection-safe dbt evaluation macros | In progress; structural checks only, executed macro proof pending |
| [REQ-030](REQ-030_runtime_failure_evidence.md) | Runtime assertion evidence and honest exception classification | Locally verified; task 5 offline, current exact-wheel qualification pending |
| [REQ-031](REQ-031_shared_controlled_failure_contract.md) | Shared controlled-operation classification and routing inspection | In progress; task 5 locally verified, connector/inspection/release gaps |
| [REQ-032](REQ-032_resolved_mutation_identity.md) | Resolved Agent identity, fresh-manifest consumption, and independent-review deploy approval fixes | In progress; review fixes locally verified, current live qualification pending |

See [user stories](user_stories.md), [test cases](../tests/test_cases.md), and
[regression coverage](../tests/regression.md) for the linked behavioral evidence.