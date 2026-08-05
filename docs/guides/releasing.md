# Releasing

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

The owner must configure both the GitHub environment and PyPI trusted publisher before the first
publication. The workflow cannot create either trust boundary.

## Release checklist

1. Choose `MAJOR.MINOR.PATCH` and update `pyproject.toml`, `dbt_project.yml`, package runtime
   version, lock metadata, citation, and current versioned documentation together.
2. Change the matching `CHANGELOG.md` heading from `Unreleased` to the release date in
   `YYYY-MM-DD` form.
3. Run the full package workflow checks locally, including `pytest -q`, package build, Twine
   metadata checks, and wheel inventory verification.
4. Commit the reviewed release preparation so the checkout is clean.
5. Create and push the immutable annotated tag `vMAJOR.MINOR.PATCH` at that commit.
6. Optionally run `Publish Python package` manually with that existing tag. Manual dispatch runs
   the preflight, critical tests, build, Twine check, wheel inventory, and artifact upload only; it
   cannot publish.
7. Create a GitHub release from the same tag and publish it. A draft or prerelease that has not
   been published does not start publication.
8. Approve the protected `pypi` environment if its rules require review. The publish job exchanges
   GitHub's short-lived OIDC identity for PyPI publication authority.
9. Perform post-publication verification: confirm the PyPI project exposes the expected version,
   verify installation in a clean environment, and confirm the Git tag still identifies the same
   dbt package version.

The release preflight requires the supplied semantic `v*` tag to point at `HEAD`, a clean checkout,
matching Python/dbt versions, and a dated changelog entry. Push and pull request events never invoke
the release workflow.
