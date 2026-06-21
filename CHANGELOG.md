# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow semantic versioning.

## [Unreleased]

### Added
- Core fail-open reduction pipeline with per-reduction fidelity scoring and deterministic output.
- Reducers: `log`, `json`, `diff`, `stacktrace`, `html`.
- Content-addressed cross-turn cache (each unique payload is reduced once).
- Integrations: `@reduce` decorator, `wrap()`, OpenAI / Anthropic / Gemini client wrappers,
  `reduce_messages` (OpenAI, Anthropic, Gemini formats), LiteLLM proxy + SDK, standalone
  FastAPI proxy, OpenTelemetry telemetry, and Anthropic native context-editing interop.
- Cost accounting (`CostTracker`, `estimate_savings`) and paging (`lc://` references + `expand`).
- Input-size guard (`CONFIG.max_input_chars`) and a global kill switch.
- Tooling: ruff, mypy, and coverage in CI; examples; contributor and security docs.

[Unreleased]: https://github.com/pankajniet/LeanContext
