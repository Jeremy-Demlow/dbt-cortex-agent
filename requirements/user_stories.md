# User stories

## REQ-002

- As a package consumer, I can identify the dbt and Python components as one product; REQ-002 established this boundary in v0.3.0 and v0.3.1 preserves it.
- As a maintainer, I can tell which layer owns each lifecycle concern and prevent Python from becoming a second Agent DDL implementation.

## REQ-003

- As a package consumer, I explicitly select the dependency source instead of inheriting a maintainer's repository URL.
- As a platform owner, I explicitly name deploy targets and allowed databases before bootstrap adds mutation-safety configuration.
- As an adopter with an established dbt project, I can preview and apply bootstrap changes without losing comments or existing configuration.

## REQ-004

- As a package consumer, I receive fresh manifest-owned Agent and eval metadata before lifecycle tooling acts.
- As a platform owner, I can prove mutation and spend target the explicitly selected connection and the database dbt resolved.
- As an evaluation maintainer, I cannot accept path-traversing, malformed, or schema-incompatible result artifacts.
- As an Agent owner, skill smoke invokes the physical Agent corresponding to each logical exposure.
- As a release operator, I can reconcile a requested alias on an unchanged deploy without minting a redundant version.

## REQ-005

- As an evaluation maintainer, I can inspect one dbt-rendered plan that exactly identifies what will be evaluated and under which policy.
- As a release operator, I can prove a candidate used one stable DEFAULT version for the complete run.
- As a baseline owner, a candidate cannot relax the accepted regression policy to pass its own comparison.
- As an evaluation operator, an applied run cannot connect until its dbt-rendered target and database are explicitly allowlisted, and it executes under the role dbt resolved.
- As a baseline owner, I can preview a deterministic migration of known legacy accepted evidence without silently overwriting a current baseline or paying for a new evaluation.

## REQ-006

- As an automation author, I can distinguish gate failure from controlled runtime failure by exit code and consume JSON without scraping human text.
- As a package consumer, I can identify every command that mutates state or spends evaluation credits before opting in with `--apply`.
- As a maintainer, I can modify one CLI domain without changing a monolithic dispatcher or expanding the package public API.
- As an installer, I use one connector extra for all runtime-backed commands and receive a clear migration path from the former extras.

## REQ-007

- As a new adopter, I can install both release surfaces and validate a project without mutating Snowflake.
- As a platform owner, I can identify each privilege and explicit apply/spend boundary before granting access or running automation.
- As an automation author, I can rely on documented commands, outputs, and exit codes that are checked against the shipped parser.
- As an upgrader from a pre-v0.3 release, I can remove copied tooling and retired extras while adopting the current package contract.
- As an installer, I can distinguish commands available after PyPI publication from the public tagged source fallback available now.

## REQ-008

- As a maintainer, I receive compatibility evidence for every supported Python and dbt line.
- As a security reviewer, I can prove default CI cannot mutate Snowflake or spend credits.
- As a release operator, I can install the exact wheel outside the source checkout and use its CLI before publishing it.
- As a consumer, I can inspect license and SBOM evidence for the verified dependency set.

## REQ-009

- As a contributor, I can understand the license and submit work without invented employer or publication approvals.
- As a maintainer, I can lead project decisions without a fabricated vacant-role block.
- As a security reporter, I retain a private reporting route.
- As a package consumer, I can rely on explicit best-effort support and technical release checks.

## REQ-010

- As a release operator, I can publish from a protected GitHub release without managing a PyPI API token.
- As a package consumer, I can trust that the PyPI and dbt Git versions identify the same release.
- As a security reviewer, I can prove that OIDC permission is isolated to the protected publish job and cannot be reached from push, pull request, or manual runs.
- As a maintainer, I can run the exact release preflight and artifact checks before publication.

## REQ-011

- As a new adopter, I can create the same synthetic Orders starter every time and prove its one Agent locally before deciding whether to connect to Snowflake.
- As an Agent operator, I can render, preview deployment, and smoke the one target-resolved Agent without requiring the Agent to have a skill or an eval model.
- As an existing consumer, I retain current metadata, lifecycle, evaluation, and skill-smoke behavior while adopting the single-Agent v0.3.1 surface.
- As a security or cost reviewer, I can prove that starter, render, deploy preview, and smoke preview do not connect, mutate state, invoke a runtime, or spend credits implicitly.
- As a release operator, I can block tutorial-skill work until the package itself passes one complete, credential-free product gate.

## REQ-013

- As an Agent owner, I deploy one physical Agent for an enabled exposure and can omit evaluation metadata without changing deployment.
- As an evaluation author, I optionally evaluate the same physical Agent users invoke without creating, cloning, suffixing, replacing, or deploying another Agent.
- As an operator, I can trace deploy and evaluation evidence to one target-resolved Agent FQN.
- As a reviewer, I can distinguish `attached`, `invoked`, `completed_with_attachment`, `absent`, and `indeterminate` capability proof.
- As a baseline owner, I retain old `_EVAL` histories for audit but do not use them as candidate or accepted baselines for the single-FQN contract.
- As an evaluation operator, I can prove the Agent existed with one DEFAULT version before START and that the same FQN and version remained authoritative through result collection.
- As an automation author, I can consume signed plan and schema-v2 artifact identity without interpreting a projection field or risking an Agent lifecycle mutation.
- As an evaluation author, I can use declared Analyst, Search, web, and generic custom tool names in native expected-tool ground truth without mistaking attached skills, MCP, or code execution for native coverage.
- As a reviewer, I can consume one general capability-evidence shape whose classification does not change the Agent specification or lifecycle identity.
- As a new adopter, I can follow an Agent-only path and add the unsuffixed Orders eval model later without creating a second Agent.
- As a project-skill user, I see manual parity for one Agent and optional evaluation authoring while all four approval boundaries remain independent.

## REQ-012

- As a new adopter, I can use Cortex Code to choose between an existing semantic view and the fixed Orders starter, with manual command parity before local writes.
- As an existing Agent owner, I can migrate its definition into a dbt-owned exposure and prove the rendered specification without copied lifecycle code.
- As an evaluation author, I can add optional manifest-owned ground truth while paid execution and baseline movement remain separate decisions.
- As a platform or cost owner, I can verify that local writes, Snowflake mutation/runtime, paid evaluation, and baseline policy each require explicit approval.
- As an installer using an immutable Git SHA, I can trust doctor to require actual installed consumer package metadata rather than accepting the package source checkout as proof.

## REQ-014

- As a release operator, I can prove the exact installed wheel works with the supported dbt lines before publication.
- As a new adopter, I can complete the Agent-only path without adding or running an evaluation.
- As an evaluation author, I can add an optional suite and prove it plans against the same Agent FQN without causing deployment.
- As a security or cost reviewer, I can inspect deterministic evidence that the verifier stays outside connector, mutation, runtime, paid evaluation, and baseline boundaries.
