# Third-Party Dependency and License Review

**Review date:** 2026-08-04  
**Status:** Metadata inventory recorded; legal approval not completed. Public publication blocked.

The dbt package contains Jinja/SQL macros and declares dbt Core `>=1.10,<2.0`; its integration
fixture directly installs `Snowflake-Labs/dbt_semantic_view`. Reference CI verifies
`dbt-snowflake==1.10.3` and `dbt-snowflake==1.11.4`. Recorded upstream metadata identifies these dependencies as
Apache-2.0, but this is not legal approval or a complete transitive inventory.

Before release, regenerate `integration_tests/package-lock.yml`, inspect resolved dbt Core,
adapter, connector, and transitive packages, verify upstream license files and copied content,
preserve required notices, and document legal approval. Unknown, incompatible,
non-redistributable, copyleft-conflicting, trademark-restricted, or notice-bearing terms block
publication until resolved.

Snowflake names describe compatibility only and do not imply sponsorship, endorsement, support,
or affiliation.