# Contributing to dbt_cortex_agent

Contributions are initially coordinated privately with the maintainers. Do not send an
unsolicited public pull request until a maintainer confirms the intake route.

Unless explicitly marked "Not a Contribution," work intentionally submitted for inclusion is
provided under Apache License 2.0 Section 5 without additional terms unless a separate written
agreement applies. Contributors retain copyright in their contributions and must preserve
accurate authorship and third-party attribution. You must be authorized by the copyright owner
and any applicable employer to submit the work.

Use synthetic fixtures and a sanitized reproduction. Remove credentials, customer or employer confidential information,
account identifiers, private object names, query results, and private URLs. Report suspected
vulnerabilities through [SECURITY.md](SECURITY.md), not an issue or pull request.

For package changes, run `dbt deps`, `dbt parse`, `dbt compile`, contract tests, and canonical
plus native-eval render/dry-run checks as applicable. Do not hand-edit generated golden files.

All merges require approval by two distinct maintainers. The second role is currently vacant,
so merge and release are blocked as described in [MAINTAINERS.md](MAINTAINERS.md). Public
publication additionally requires the employer-rights and legal review in
[GOVERNANCE.md](GOVERNANCE.md). Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

This package is independent and is not sponsored, endorsed, supported, or maintained by
Snowflake Inc.