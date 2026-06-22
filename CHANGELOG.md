# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow semantic versioning.

## [Unreleased]

## [2.1.0] - 2026-06-22

### Fixed
- Fidelity checks now match values as whole tokens instead of substrings, so the gate
  no longer over-reports preservation and lets real loss through:
  - **JSON**: scalar values are matched as a multiset of whole JSON-encoded tokens.
    A dropped value that is a substring of a survivor (e.g. `"1"` inside `"100"`), or a
    dropped duplicate, now lowers the score instead of counting as preserved.
  - **HTML**: visible text is matched on distinct whole words. A flood of common words
    (`the`, `on`, …) no longer masks the loss of a few rare-but-important ones, and
    `cat` no longer counts as present because the output contains `category`.
  - **Stack traces**: every exception message and chain marker must survive, not only
    the last line. A *chained* traceback whose earlier root cause is collapsed now
    scores low and reverts (fail-open) instead of silently dropping the cause.
- Diff detection no longer fires on prose that merely contains an `@@ … @@`-shaped line:
  a hunk header now counts as a diff only when accompanied by actual `+`/`-` change
  lines, so the context-collapsing reducer can't run on non-diff text.

## [2.0.8] - 2026-06-21

### Fixed
- Table reducer no longer corrupts values. It used to collapse every run of 2+ spaces,
  silently mangling any value with internal double-spaces (and fidelity, which used the
  salience check, reported 100%). It now detects column boundaries, slices each row into
  cells, and drops only each cell's trailing alignment padding — internal spaces are kept.
- Table fidelity is now content-aware (`_table_fidelity`): it verifies every row's
  non-space content survives, so a dropped row or lost character trips the gate.
- `Reduction.ratio` is clamped at 0, so a reverted longer result can't report a negative
  ratio (now consistent with `tokens_saved`).
- Changing the tokenizer (`set_token_counter` / `use_tiktoken`) clears the reduction
  cache, so cached token counts and revert decisions can't go stale.

## [2.0.7] - 2026-06-21

### Fixed
- HTML fidelity is now content-aware: it measures the fraction of the original's
  visible-text words kept in the output (reusing the HTML reducer's own extractor),
  so dropped body text lowers the score and trips the fidelity gate. The previous
  salience-based check returned 1.0 for lost prose that contained no error keyword.
  Correct strips still score ~1.0 and reduce as before.

## [2.0.6] - 2026-06-21

### Fixed
- JSON reducer is now lossless on every value: rows are emitted as JSON arrays with
  the field names factored into the header once, so values containing the column
  delimiter, quotes, or newlines no longer corrupt the columnar layout. The JSON
  fidelity check matches values in their encoded form, so it sees such corruption.
- Gateway paths (LiteLLM proxy + SDK patch) now reduce OpenAI Responses requests
  (`input=`), not just chat (`messages=`).
- `reduce_messages` dispatches per item, so a list mixing message formats reduces
  every tool output instead of only those matching the first format detected.
- OpenAI Responses tool outputs shaped as a list of content parts are now reduced.
- `__version__` is read from the installed package metadata (was a stale `0.0.1`).
- `CostTracker` running totals are guarded by a lock for multi-threaded agents.

### Docs
- README install commands use the published package (`pip install leancontext`),
  document the `mcp` extra, note which tokenizer the benchmark uses, and state
  which integrations are CI-verified vs best-effort.

## [2.0.5] - 2026-06-21

### Security
- Fix a path traversal in the disk-backed paging store: `expand()` and `ContentStore.get()`
  now accept only content-hash ids, so a crafted reference can no longer read files outside
  the store (reachable via the MCP `expand` tool). The default in-memory store was unaffected.

## [2.0.4] - 2026-06-21

### Fixed
- README uses absolute image and link URLs so the logo and links render on the PyPI
  project page (relative paths only resolve on GitHub).
- The reduction cache is now thread-safe (guarded by a lock) for multi-threaded agents.

### Added
- OpenAI Responses API support: `reduce_messages` and `wrap_openai` handle `input`
  with `function_call_output` items.
- PyPI downloads badge, `SUPPORT.md`, and a CodeQL security-scanning workflow.

## [2.0.2] - 2026-06-21

### Changed
- Lower the minimum Python from 3.14 to 3.10 so the package installs on current
  interpreters (the code already supports 3.10+; CI runs 3.10 through 3.14).

## [2.0.1] - 2026-06-21

Intermediate release during the initial PyPI rollout (Python version metadata),
superseded by 2.0.2. Version 2.0.3 was never published.

## [2.0.0] - 2026-06-21

### Added
- Core fail-open reduction pipeline with deterministic output and per-content-type
  fidelity scoring (json, diff, and stack-trace reductions are verified, not assumed).
- Reducers: `log`, `json`, `diff`, `stacktrace`, `html`, and `table` (whitespace-aligned
  command-line output). Each reducer declares its own detector via a small registry.
- Content-addressed cross-turn cache (each unique payload is reduced once).
- Integrations: `@reduce` decorator and `wrap()` (sync and async tools); OpenAI / Anthropic /
  Gemini client wrappers; `reduce_messages` (OpenAI, Anthropic, Gemini formats); LiteLLM
  proxy + SDK; a hardened standalone FastAPI proxy (auth passthrough, streaming, 502 on
  upstream errors); OpenTelemetry telemetry; Anthropic native context-editing interop;
  an MCP server (`reduce`/`expand`/`stats`); and framework adapters for LangChain,
  LangGraph, and Agno.
- Cost accounting (`CostTracker`, `estimate_savings`) and paging (`lc://` references + `expand`).
- Token counting auto-uses `tiktoken` when installed, with `active_tokenizer()` to report it.
- A caching-on validation harness (`examples/validate_caching.py`) for Anthropic and OpenAI.
- Input-size guard (`CONFIG.max_input_chars`) and a global kill switch.

### Project
- Targets Python 3.14; ruff, mypy, and coverage run in CI; examples, contributor, and
  security docs included.

[Unreleased]: https://github.com/pankajniet/LeanContext/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/pankajniet/LeanContext/releases/tag/v2.1.0
[2.0.8]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.8
[2.0.7]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.7
[2.0.6]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.6
[2.0.5]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.5
[2.0.4]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.4
[2.0.2]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.2
[2.0.1]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.1
[2.0.0]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.0
