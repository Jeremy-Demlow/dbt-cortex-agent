# Public content policy

This repository contains public product code, synthetic examples, and reusable
engineering evidence. Tracked content must not depend on a maintainer's
workstation, Snowflake account, employer-only implementation, or live customer
or operational environment.

## Allowed

- Public Snowflake product names and documented terms, including internal
  stages, Cortex Agents, Cortex Search, Semantic Views, and DCM.
- Clearly synthetic databases, roles, users, account identifiers, errors, and
  fixture data.
- Jeremy Demlow as maintainer and the public `Jeremy-Demlow` GitHub namespace.
- Immutable coordinates for public commits and releases.

## Prohibited

- Real Snowflake account identifiers, users, hosts, connection names, private
  URLs, OIDC subjects, network policies, or service-account details.
- Employee email addresses, credentials, secrets, raw prompts, query results,
  traces, or customer data.
- Absolute workstation paths or generated local state such as `.user.yml`.
- Live object inventories, run identifiers, timestamps, hashes, or metrics that
  reveal a specific operational environment.
- Employer-only package names, codenames, or copied internal implementation
  details.

Security reports use GitHub's private vulnerability reporting for this
repository. Public issues must never contain sensitive information.