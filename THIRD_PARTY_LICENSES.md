# Third-Party Dependency and License Review

**Review date:** 2026-08-04  
**Status:** Metadata inventory recorded; verify the resolved dependency inventory before release.

The dbt package contains Jinja/SQL macros and declares dbt Core `>=1.10,<2.0`; its integration
fixture directly installs `Snowflake-Labs/dbt_semantic_view`. Reference CI verifies
`dbt-snowflake==1.10.3` and `dbt-snowflake==1.11.4`. Recorded upstream metadata identifies these dependencies as
Apache-2.0, but this is not a complete transitive inventory.

Before release, regenerate `integration_tests/package-lock.yml`, inspect resolved dbt Core,
adapter, connector, and transitive packages, verify upstream license files and copied content,
preserve required notices, and resolve unknown, incompatible, non-redistributable,
copyleft-conflicting, trademark-restricted, or notice-bearing terms before release.

Snowflake names describe compatibility only and do not imply sponsorship, endorsement, support,
or affiliation.