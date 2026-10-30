# Releasing

Releases are tag-triggered by `.github/workflows/release.yml`. Publishing uses
PyPI trusted publishing (OIDC, no tokens) through the GitHub environment `pypi`.

## One-time maintainer prerequisites

Do these in order, before the first tag.

1. **Rename the GitHub repo to `server-motd`** (Settings > General > Repository
   name). Do this first: the PyPI trusted publisher is bound to the repository
   name, so registering it before the rename would bind the wrong name.
2. **Create the GitHub environment `pypi`** (Settings > Environments). Optionally
   require a reviewer for manual approval of each publish.
3. **Register a pending publisher on PyPI** (pypi.org > Your account > Publishing
   > Add a new pending publisher) with:
   - PyPI project name: `server-motd`
   - Owner: the GitHub owner of the repo
   - Repository name: `server-motd`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
4. Allow Actions to open pull requests (Settings > Actions > General > Workflow
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

The Ansible role installs the package from a hash-pinned lockfile. Assumed
location: `ansible/roles/server_motd/files/requirements.lock` (a placeholder until the first release, which the lockfile PR then fills; the role refuses to install from a lockfile without a `server-motd==` pin).
After publishing, the `lockfile-pr` job regenerates it with
`pip-compile --generate-hashes` for `server-motd==<version>` and opens a PR
against `master`. If the file does not exist yet the job logs a notice and does
nothing; if #29 uses a different path, update `LOCKFILE` in `release.yml`.
