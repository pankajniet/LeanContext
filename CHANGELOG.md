# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow semantic versioning.

## [Unreleased]

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

[Unreleased]: https://github.com/pankajniet/LeanContext/compare/v2.0.2...HEAD
[2.0.2]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.2
[2.0.0]: https://github.com/pankajniet/LeanContext/releases/tag/v2.0.0
