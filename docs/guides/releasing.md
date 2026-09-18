# Releasing

## Live qualification

A published release is not sent directly from build to PyPI. The release workflow
passes the exact wheel artifact through the protected `snowflake-live-ci`
environment first:

```text
[tag checkout] -> [tests + sdist/wheel + wheel SHA-256]
       -> [protected exact-wheel multi-database proof]
       -> [PyPI trusted publication]
```

The live job uses only dedicated non-production proof databases and runs cleanup
under `always()`. Its retained attestation is whitelist-only: wheel hash, target,
observed physical Agent FQNs for both databases, versions and aliases, before/after
reconciliation snapshots, evaluation database, `paid_evaluation: false`, independent
`proof_status` and `cleanup_status`, and bounded exception types on failure.
`agents` retains the last observed pre-retirement states, not a claim that those
Agents still exist. Cleanup-only updates preserve proof results and refuse
mismatched target/database/wheel evidence. Cleanup success without prior proof
has `proof_status: not_started`; failed proof stays failed even after cleanup.
Top-level `status` cannot be completed if proof or cleanup failed. Cleanup
completion means all bounded DROP commands returned successfully, not an
independent post-cleanup inventory. Manual workflow dispatch validates/builds an existing tag but
cannot publish and does not invoke the release-only live gate.

This proof invokes Agents and uses a warehouse, so it can incur runtime/compute
costs. `paid_evaluation: false` means only that native Agent Evaluation was not
started: eval verification is preview-only. It is not free-runtime or paid-quality
qualification. Paid evaluation requires its own approval and retained evidence.

The GitHub `release: published` event starts this workflow. The protected proof
therefore gates PyPI publication, not creation of the GitHub release record.

The proof runner always sets child `DBT_EXECUTABLE` to its created
`<artifact_dir>/venv/bin/dbt`, matching direct dbt commands and the pinned install.
Inherited executable overrides cannot substitute a host dbt. The same environment
is used for lifecycle and cleanup; cleanup-only invokes bounded Snow CLI commands,
so it does not need the dbt venv to survive a failed setup. Local test harnesses
must fake the isolated executable or subprocess boundary, not depend on a host
fallback. A fake setup that leaves dbt missing must fail proof, not qualify it.

Python distributions publish through GitHub OIDC trusted publishing. Do not create or configure a
PyPI API token for this workflow. The dbt package remains the same source tree at the matching Git
tag because `dbt deps` does not install packages from PyPI.

## One-time owner setup

1. Create or claim the `dbt-cortex-agent` project on PyPI using the project owner's PyPI account.
2. In the GitHub repository, create an environment named exactly `pypi`. Add required reviewers
   and deployment protection rules appropriate for package publication.
3. In the PyPI project's publishing settings, add a GitHub trusted publisher with:
   - owner: `Jeremy-Demlow`
   - repository: `dbt-cortex-agent`
   - workflow: `release.yml`
   - environment: `pypi`
4. Do not add `PYPI_API_TOKEN`, a PyPI password, or another publication credential to GitHub.
5. Create the separate protected `snowflake-live-ci` environment with required
   reviewers and reviewed branch/tag deployment restrictions. Both live-integration
   and release workflows use this environment; review the scheduled live lane too.
6. Configure its secrets `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, and
   `SNOWFLAKE_PRIVATE_KEY` for the dedicated JWT service identity. The workflow
   writes temporary key material with restrictive permissions and removes it under
   `always()`. Never put keys in dbt metadata or attestation artifacts.
7. Configure environment variables `SNOWFLAKE_LIVE_ROLE`,
   `SNOWFLAKE_LIVE_WAREHOUSE`, `SNOWFLAKE_LIVE_DATABASE_A`,
   `SNOWFLAKE_LIVE_DATABASE_B`, and `SNOWFLAKE_LIVE_EVAL_DATABASE`. Use three
   distinct non-production databases and match the integration consumer's reviewed
   database allowlist; the default names are `DBT_CORTEX_AGENT_SANDBOX_A`,
   `DBT_CORTEX_AGENT_SANDBOX_B`, and `DBT_CORTEX_AGENT_SANDBOX_EVAL`.
8. Provision the proof schemas, warehouse, authentication, and least-privilege
   create/alter/drop/runtime/dependency access outside the package. Reserve the
   exact proof-object names, verify a clean starting state, and approve bounded
   cleanup. The integration fixture intentionally overrides dbt schema naming;
   do not confuse it with the default-schema installed-consumer proof.

The owner must configure both GitHub environments and the PyPI trusted publisher
before publication. The workflow cannot create these trust boundaries.

## Release checklist

1. Choose `MAJOR.MINOR.PATCH` and update `pyproject.toml`, `dbt_project.yml`, package runtime
   version, lock metadata, citation, and current versioned documentation together.
2. Change the matching `CHANGELOG.md` heading from `UNRELEASED` to the new version and release date in
   `YYYY-MM-DD` form.
3. Run full offline tests/combined coverage, global Ruff format/check, mypy,
   mutation gate, package build, Twine, and wheel inventory checks. Qualify the
   exact wheel in clean installed consumers on both supported dbt lines, including
   default schema generation. A no-isolation local build or mocked verifier unit
   test is not that installation proof. Keep unrun checks explicitly pending.
4. Commit the reviewed release preparation so the checkout is clean.
5. Create and push the immutable annotated tag `vMAJOR.MINOR.PATCH` at that commit.
6. Optionally run `Publish Python package` manually with that existing tag. Manual dispatch runs
   the preflight, critical tests, build, Twine check, wheel inventory, and artifact upload only; it
   cannot publish.
7. Create a GitHub release from the same tag and publish it. A draft or prerelease that has not
   been published does not start publication.
8. Approve `snowflake-live-ci`, inspect the exact wheel hash, both Agent states,
   proof and cleanup outcomes, and require the live job to succeed. Separately
   approve the protected `pypi` environment if its rules require review. The publish job exchanges
   GitHub's short-lived OIDC identity for PyPI publication authority.
9. Perform post-publication verification: confirm the PyPI project exposes the expected version,
   verify installation in a clean environment, and confirm the Git tag still identifies the same
   dbt package version.

The release preflight requires the supplied semantic `v*` tag to point at `HEAD`, a clean checkout,
matching Python/dbt versions, and a dated changelog entry. Push and pull request events never invoke
the release workflow.

The current `0.0.9` candidate is dated 2026-09-18 and pending qualification and
publication. Its dated changelog and updated install examples do not mean it is
already released. Do not rewrite the existing `0.0.8` distribution or move `v0.0.8`.
The owner approved finishing commit, push, qualification, and release after gates;
this preparation slice performs only local version edits and offline checks.
Exact-wheel clean-install qualification on both supported dbt lines, protected live
proof, and publication remain pending. Git mutation and network/live execution are
outside this slice; a local passing test suite does not satisfy those gates.
