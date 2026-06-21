# Releasing LeanContext

A short checklist for cutting a release to PyPI. Building and metadata checks are
done; the only step that needs your credentials is the final upload.

## 1. Pre-release checks

```bash
ruff check leancontext bench.py demo.py
mypy leancontext
pytest -q
python bench.py        # sanity-check the numbers in the README
```

## 2. Set the version

Bump `version` in `pyproject.toml` (first public release is usually `0.1.0`) and move the
`CHANGELOG.md` entries from `[Unreleased]` into a dated section for that version.

## 3. Build and validate

```bash
rm -rf dist
uv build                     # or: python -m build
uvx twine check dist/*       # or: twine check dist/*
```

Both the wheel and sdist should report `PASSED`. The wheel includes `py.typed` and every
submodule.

## 4. Upload

Test on TestPyPI first, then the real index (needs a PyPI API token):

```bash
uvx twine upload --repository testpypi dist/*
uvx twine upload dist/*
```

## 5. Tag

```bash
git tag v0.1.0
git push origin v0.1.0
```
