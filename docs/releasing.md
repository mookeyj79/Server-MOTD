# Releasing

Releases are tag-triggered by `.github/workflows/release.yml`. Publishing uses
PyPI trusted publishing (OIDC, no tokens) through the GitHub environment `pypi`.

## One-time maintainer prerequisites

Do these in order, before the first tag.

1. **Create the GitHub environment `pypi`** (Settings > Environments). Optionally
   require a reviewer for manual approval of each publish.
2. **Register a pending publisher on PyPI** (pypi.org > Your account > Publishing
   > Add a new pending publisher) with:
   - PyPI project name: `server-motd`
   - Owner: the GitHub owner of the repo
   - Repository name: `Server-MOTD` (the GitHub repo name; only the PyPI project is lowercase)
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. Allow Actions to open pull requests (Settings > Actions > General > Workflow
   permissions > "Allow GitHub Actions to create and approve pull requests"),
   needed by the post-release lockfile PR.

## Cutting a release

1. Set `version` in `pyproject.toml` and add a `## [x.y.z]` section to
   `CHANGELOG.md`; merge to `master`.
2. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. The workflow verifies the tag matches `pyproject.toml` and the changelog,
   runs ruff, mypy and pytest, builds, publishes to PyPI, creates the GitHub
   Release (notes from the changelog section, dist files attached) and opens a
   lockfile PR.

## Post-release lockfile PR

The Ansible role installs the package from a hash-pinned lockfile,
`ansible/roles/server_motd/files/requirements.lock` (a placeholder until the
first release, which the lockfile PR then fills; the role refuses to install
from a lockfile without a `server-motd==` pin).
After publishing, the `lockfile-pr` job regenerates it with
`pip-compile --generate-hashes --strip-extras` for
`server-motd[figlet]==<version>` (the role always installs the figlet banner)
and opens a PR against `master` in this repository (`--repo` is explicit
because the repo is a fork). If the file does not exist, the job logs a notice
and does nothing.

PyPI's index can take a few minutes to list a new version, so the job retries
`pip-compile` for up to about 10 minutes, bypassing pip's cache (PyPI's index
pages are cacheable for 10 minutes, which would otherwise make every retry
see the same stale page). If it still fails, re-run just that job once the
version shows on PyPI: `gh run rerun <run-id> --failed` (publishing is not
repeated).

GitHub does not start `pull_request` workflows for a PR opened with the
workflow's own token, so the job then dispatches `ci.yml` on the lockfile
branch (`workflow_dispatch` runs are the exception). Its checks show on the
PR as usual; wait for them before merging.
