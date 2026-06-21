# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow semantic versioning.

## [Unreleased]

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

[Unreleased]: https://github.com/pankajniet/LeanContext/compare/v2.0.5...HEAD
[2.0.5]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.5
[2.0.4]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.4
[2.0.2]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.2
[2.0.0]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.0
