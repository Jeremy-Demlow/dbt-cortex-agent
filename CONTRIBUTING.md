# Contributing to dbt_cortex_agent

Issues and pull requests are welcome. Keep changes focused, link the applicable requirement or
state an independently testable outcome, and include verification evidence.

Unless explicitly marked "Not a Contribution," work intentionally submitted for inclusion is
provided under Apache License 2.0 Section 5 without additional terms unless a separate written
agreement applies. Contributors retain copyright in their contributions and must preserve
accurate authorship and third-party attribution. Submit only work you have the right to license.

Use synthetic fixtures and a sanitized reproduction. Remove credentials, customer or organization confidential information,
account identifiers, private object names, query results, and private URLs. Report suspected
vulnerabilities through [SECURITY.md](SECURITY.md), not an issue or pull request.

For package changes, run `dbt deps`, `dbt parse`, `dbt compile`, contract tests,
full-Agent render/dry-run checks, and optional eval-plan checks as applicable. Do
not hand-edit generated golden files.

Maintainers review contributions for scope, correctness, security, licensing, and test evidence
before merging. Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

This package is independent and is not sponsored, endorsed, supported, or maintained by
Snowflake Inc.