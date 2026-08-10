# Requirements index

Requirements are the product contract. A requirement is complete only when its acceptance criteria
have reproducible verification evidence. Historical version-specific requirements remain indexed as
the provenance of the current package; current release scope is v0.3.1.

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
| [REQ-011](REQ-011_tutorial_product_readiness.md) | Orders starter, projection render/deploy, and Agent smoke | Complete (v0.3.1) |
| [REQ-012](REQ-012_guided_cortex_code_adoption_skill.md) | Guided Cortex Code adoption and immutable-SHA doctor | Complete (v0.3.1) |
| [REQ-013](REQ-013_single_physical_agent_evaluation.md) | One physical Agent per enabled exposure and target, with optional same-Agent evaluations | Complete |
| [REQ-014](REQ-014_installed_wheel_single_agent_verifier.md) | Installed-wheel Agent-only and optional-eval end-to-end verification | Complete |

See [user stories](user_stories.md), [test cases](../tests/test_cases.md), and
[regression coverage](../tests/regression.md) for the linked behavioral evidence.