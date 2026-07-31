# Installation

## Current embedded-package installation

Add a local dependency from the consuming dbt project:

```yaml
packages:
  - local: ../packages/dbt_cortex_agent
```

Run:

```bash
dbt deps
dbt parse
```

The relative path is resolved from the consuming project's directory. A clean
checkout has no `dbt_packages/`, so `dbt deps` is required.

## Private Git release

The standalone package is released privately at `Jeremy-Demlow/dbt-cortex-agent`.
After the v0.2.0 tag is pushed and verified, use the pinned Git dependency:

```yaml
packages:
  - git: "git@github.com:Jeremy-Demlow/dbt-cortex-agent.git"
    revision: v0.2.0
```

The consuming environment must have access to the private repository. There is no
dbt Hub coordinate in this release. Do not use an unpinned branch.

## Dependencies

The package itself ships macros and a generic test. Consumers using Analyst tools
must separately install a compatible semantic-view package, for example:

```yaml
packages:
  - local: ../packages/dbt_cortex_agent
  - package: Snowflake-Labs/dbt_semantic_view
    version: 1.0.5
```

Python/Snow CLI skill and CI tools are optional framework assets and are not dbt
package dependencies.
