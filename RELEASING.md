# Releasing LeanContext

The smooth path uses **PyPI Trusted Publishing**: GitHub Actions publishes to PyPI over
OIDC, so there are no API tokens to create, store, or paste. You set it up once, then every
release is just "publish a GitHub Release."

## One-time setup

On PyPI, register this repo as a trusted publisher (works before the project exists):

1. Open <https://pypi.org/manage/account/publishing/>.
2. Under **Add a new pending publisher**, enter:
   - PyPI Project Name: `leancontext`
   - Owner: `pankajniet`
   - Repository name: `LeanContext`
   - Workflow name: `publish.yml`
   - Environment: *(leave blank)*
3. Save.

The workflow lives at `.github/workflows/publish.yml` and runs when a GitHub Release is published.

## Cutting a release

1. Bump `version` in `pyproject.toml` and move the `CHANGELOG.md` entries from `[Unreleased]`
   into a dated section.
2. Sanity-check, then commit and push to `main`:
   ```bash
   ruff check leancontext && mypy leancontext && pytest -q
   git push
   ```
3. On GitHub: **Releases → Draft a new release → tag `vX.Y.Z` → Publish.**

Publishing the release triggers `publish.yml`, which builds the wheel + sdist and uploads them
to PyPI. After it finishes, `pip install leancontext` works.

## Manual fallback (token-based)

If you ever need to publish from your machine instead:

```bash
rm -rf dist
uv build
uvx twine check dist/*
uvx twine upload dist/*      # username = __token__   password = <your PyPI token>
```
