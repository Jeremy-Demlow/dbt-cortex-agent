# User stories

## REQ-021

- As a maintainer, I can reason about immutable validated domain values instead of loosely shaped dictionaries.
- As a contributor, I receive fast lint, type, complexity, property, and test feedback before release.
- As a consumer, expected failures are bounded, actionable, and never expose a traceback or secret.

## REQ-022

- As an operator, all selected resources are authorized before the first durable effect.
- As an automation author, I receive structured evidence for every completed and failed phase.
- As an adopter, I use package-native deployment and evaluation without copied sequencers.

## REQ-023

- As a dbt developer, I have one real documented macro surface and one reconciliation process.
- As an operator, retries converge from observed Snowflake state after partial durable work.
- As a maintainer, I can delete orphaned legacy code rather than preserve a second broken lifecycle.

## REQ-024

- As a new developer, I can scaffold a valid Agent without already having a Semantic View.
- As an Analyst user, I can optionally connect a uniquely resolved Semantic View model.
- As an experimental-feature user, arbitrary experimental settings survive render and reconciliation without package-specific private-preview APIs.

## REQ-025

- As a release operator, I can inspect, promote, roll back, and roll forward immutable Agent versions.
- As an incident responder, I can route traffic to an older version without deleting newer history.
- As an evaluator, I can prove the exact version that answered and was evaluated.

## REQ-026

- As an owner, I can intentionally retire a manifest-owned Agent with exact destructive confirmation.
- As a reviewer, I can see what is deleted and what remains before approving the operation.
- As a platform owner, deleting a dbt model cannot silently delete a deployed Agent.

## REQ-027

- As a developer, asking an Agent returns a concise answer and useful execution summary rather than a huge protocol dump.
- As an automation author, I receive stable normalized JSON and can opt into bounded raw evidence.
- As a maintainer, one tested protocol kernel supports smoke, skills, and future clients.

## REQ-028

- As a developer, I can follow one executable path from scaffold to CI/CD without repository-specific wrappers.
- As a platform owner, I can identify each privilege, approval, mutation, runtime, and spend boundary.
- As an article author, I can trace every technical claim to repeatable package evidence.

## REQ-016

- As a runtime operator, I can declare roles that receive `USAGE ON AGENT` without putting grants in the Agent specification.
- As an evaluation operator, I can declare a role under both usage and monitor access so asynchronous Agent evaluation tasks receive Snowflake's required Agent privileges.

## REQ-017

- As an Agent operator, I can declare the roles that receive `USAGE` on each pre-existing Cortex Search Service used by an Agent tool.
- As an evaluation operator, missing tool access blocks before paid ingestion and identifies the exact tool dependency.

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
- As an installed-package consumer, I can render an eval plan under supported dbt versions without consumer macro namespace or dispatch ambiguity.

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

## REQ-015

- As an operator, one explicit Snow CLI connection controls dbt rendering, stage operations, runtime invocation, and evaluation.
- As a security reviewer, connection secrets remain in memory and are never printed, persisted, or copied into command arguments.
- As a maintainer, unsupported authentication modes fail before any dbt or Snowflake operation begins.

## REQ-019

- As a package maintainer, I can prove the exact wheel deploys same-named Agents in two approved databases without identity collision.
- As a release operator, PyPI publication cannot use an artifact different from the wheel that passed protected live proof.
- As a security reviewer, ordinary PR CI remains credential-free and live proof is isolated behind a protected environment.
- As an operator, a second identical build proves no redundant Agent version is created and cleanup remains safe after partial failure.

## REQ-020

- As a new adopter, I can deploy and verify a dbt-owned Agent using released package commands without copying a Makefile or Python sequencer.
- As an Agent owner, one preview shows the exact physical Agents, skills, dependencies, and databases before mutation.
- As an evaluation owner, one command materializes the dataset, runs the paid evaluation, consumes the exact candidate, and applies intrinsic or accepted-baseline policy.
- As an automation author, quality failures and infrastructure failures have distinct stable exits and structured evidence.

## REQ-029

- As a dbt operator, every documented evaluation macro path resolves only shipped macro helpers.
- As a security reviewer, an unsafe run name cannot be concatenated into evaluation SQL.
- As a maintainer, unreachable legacy Agent branches do not conceal undefined behavior.

## REQ-030

- As an Agent operator, a failed expected-tool assertion preserves the normalized response that explains the failure.
- As a cost owner, an existing raw-evidence filename fails before another runtime call is made.
- As a developer, programming defects remain visible rather than being mislabeled as recoverable operational failures.
- As a multi-database operator, connection context does not silently narrow manifest-derived resource authorization.
- As a platform owner, infrastructure tooling and fleet authorization remain adopter policy rather than package dependencies.
