# Contributing to LeanContext

Thanks for your interest. Issues and pull requests are welcome.

## Setup

```bash
pip install -e ".[dev,otel,integrations]"
```

## Before you push

```bash
ruff check leancontext bench.py demo.py    # lint
mypy leancontext                           # types
pytest -q                                  # tests
```

CI runs all three on Python 3.10 through 3.14.

## Writing a reducer

Reducers live in `leancontext/reducers/` and are pure functions:

```python
def reduce_x(text: str) -> tuple[str, list[str]]:
    ...
    return reduced_text, notes
```

They must be:

- **Deterministic** — the same input always produces the same output (the cache and prompt
  caching depend on this; there is a determinism test for every reducer).
- **Value-preserving** — never silently drop identifiers, numbers, paths, or error lines.
- **Anomaly-preserving** — rare and error/severity lines are the signal; keep them.

Register the reducer and its detector in `leancontext/core.py`, and add tests covering ratio,
determinism, and signal preservation.

## Design rules

See [AGENTS.md](AGENTS.md) for the full contract (fail-open behaviour, the no-LLM rule,
integration principles, and what LeanContext deliberately does not do).

## Commit messages

Plain, descriptive summaries. No AI co-author trailers.
