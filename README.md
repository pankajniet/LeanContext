<p align="center">
  <img src="assets/logo.png" alt="LeanContext" width="460">
</p>

<p align="center">
  <b>Cut AI-agent token costs by trimming the tool output you re-send every turn —<br>
  deterministically, with a fidelity score on every reduction, and never breaking the agent.</b>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue.svg">
  <a href="https://github.com/pankajniet/LeanContext/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/pankajniet/LeanContext/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="status: alpha" src="https://img.shields.io/badge/status-alpha-orange.svg">
</p>

---

**LeanContext** sits between your agent and the model and shrinks the bloated tool outputs —
logs, JSON/RAG chunks, diffs, stack traces, HTML — that get re-sent to the model on every turn.

It is built around three properties most context-compressors don't guarantee:

- **Deterministic** — the same input always reduces to the same bytes, so it never busts the
  provider's prompt cache (which is where a naive compressor can quietly *raise* your bill).
- **Measurable** — every reduction returns a fidelity score; if the signal isn't preserved
  above a threshold, the original is returned unchanged.
- **Fail-open** — unknown content, a reducer error, or a low score all fall back to the original.
  LeanContext can only help or do nothing; it can never corrupt the agent's context.

No LLM in the reduction path: it's pure, fast, and free of per-call model cost or language bias.

```python
from leancontext import reduce

@reduce                          # one line — the agent never knows it's there
def search_logs(query: str) -> str:
    return run_log_search(query) # ~10k tokens of logs in → ~1k out, error lines kept verbatim
```

## Why this matters

- In agentic workloads, the model API is **70–85% of total cost**, and most of that is *input* tokens.
- A tool result added on turn *N* is **re-sent on every later turn**, so cost grows with the
  length of the conversation, not just the work done.
- Those payloads are mostly redundancy: repeated timestamps, JSON keys, boilerplate, near-identical lines.

LeanContext keeps the signal (errors, anomalies, identifiers) and drops the rest.

## Results

Reproduce with `python bench.py` (representative tool outputs, heuristic token count):

| Payload          |   Before |  After | Saved | Fidelity |
| ---------------- | -------: | -----: | ----: | -------: |
| Incident log     |   26,766 |     55 |  100% |     100% |
| RAG / JSON       |    1,706 |  1,247 |   27% |     100% |
| HTML page        |    1,528 |  1,156 |   24% |     100% |
| Diff             |      592 |     58 |   90% |     100% |
| Stack trace      |      618 |     72 |   88% |     100% |
| **Total**        | **31,210** | **2,588** | **92%** | **100%** |

Because the cost is paid *every turn the payload stays in context*, the real saving is this
multiplied by the number of turns it's held.

## How it's different

- **vs. LLM-based prompt compressors** — there's no model in the reduction path, so it's
  deterministic, adds no latency or per-call cost, has no language bias, and can't "compress
  away" the wrong thing. It also won't bust the provider's prompt cache.
- **vs. wire-level proxies** — it reduces at the source, where the content type is still known,
  so it's type-aware: it keeps error/anomaly lines verbatim and never edits your instructions.
- **vs. doing nothing** — large, safe savings on the payloads that dominate agent cost, and it
  *composes* with prompt caching and Anthropic's native context editing rather than fighting them.

## Install

```bash
pip install -e .                  # core, standard library only
pip install -e ".[tiktoken]"      # exact token counts
pip install -e ".[otel]"          # OpenTelemetry metrics
pip install -e ".[integrations]"  # openai / anthropic / litellm / fastapi adapters
```
> Not yet on PyPI — install from source for now.

## Usage

Pick the integration level that fits; all share one core and all fail open.

```python
import leancontext

# 1) Manual — works anywhere
clean = leancontext.reduce(tool_output).text

# 2) Decorator — one line per tool
@leancontext.reduce
def search_logs(q: str) -> str:
    ...

# 3) Wrap all tools, or an SDK client — one line, any framework
tools  = leancontext.wrap(tools)
client = leancontext.wrap(openai_client)   # also wrap_anthropic / wrap_gemini
```

Each reduction is inspectable:

```python
r = leancontext.reduce(tool_output)
r.text                       # what to send to the model
r.tokens_before, r.tokens_after
r.ratio                      # fraction saved
r.fidelity                   # 0..1 signal preserved
r.kind, r.ref                # detected type, content hash
```

## Integrations

| Surface | How |
| --- | --- |
| Decorator / tools | `@leancontext.reduce`, `leancontext.wrap(tools)` |
| OpenAI / Anthropic / Gemini SDK | `wrap_openai(client)` · `wrap_anthropic(client)` · `wrap_gemini(client)` |
| LiteLLM (proxy) | `callbacks: leancontext.integrations.litellm.proxy_handler_instance` |
| LiteLLM (SDK) | `import leancontext.integrations.litellm as ll; ll.patch()` |
| Standalone proxy | `from leancontext.integrations.proxy import create_app` (OpenAI-compatible, any language) |
| Wire / messages | `leancontext.reduce_messages(messages)` (OpenAI, Anthropic, Gemini) |
| Telemetry | `import leancontext.integrations.otel as o; o.instrument()` (OpenTelemetry GenAI conventions) |
| Anthropic native | `wrap_anthropic_native(client, ...)` — composes with `clear_tool_uses` context editing |

## Reducers

| Kind | What it does |
| --- | --- |
| `log` | Collapse near-identical lines; keep every error/anomaly/unique line verbatim |
| `json` | Factor repeated keys out once, values laid out columnar (near-lossless) |
| `diff` | Keep all change/hunk/header lines; collapse unchanged context |
| `stacktrace` | Keep the exception and boundary frames; collapse the deep middle |
| `html` | Strip tags/scripts/styles; keep visible text and links |

Anything else, or any payload below the size/saving/fidelity thresholds, passes through unchanged.

## How it works

Each tool output flows through a series of fail-open gates — hash, size check, type detection,
typed reducer, then a saving/fidelity check — and returns either the reduced text or the original.
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for diagrams.

## Cost & telemetry

```python
from leancontext.cost import CostTracker
tracker = CostTracker(model="claude-sonnet-4-6").install()
# ... run your agent ...
tracker.report()   # {tokens_saved, usd_saved, ratio, cache_safe: True}
```

## Configuration

```python
leancontext.disable()                       # global kill switch (or env LEANCONTEXT_DISABLED=1)
leancontext.reduce(x, min_saving=0.1, min_fidelity=0.85)
leancontext.on_reduction(callback)          # telemetry hook (composable)
leancontext.use_tiktoken("gpt-4o")          # exact token counts
```

## Roadmap

- Real-agent validation with prompt caching enabled (measure the marginal saving)
- Cross-turn reduction cache (reduce each unique output once)
- MCP server surface; tested LangChain / LlamaIndex / CrewAI adapters
- Paging tier polish (reversible `lc://` references + `expand` tool)
- PyPI release

## Contributing

Issues and PRs welcome. Run the suite with `pytest`. Reducers are pure functions
(`str -> (reduced, notes)`) and must be deterministic and value-preserving; see `AGENTS.md`
for the design rules.

## License

[Apache-2.0](LICENSE).
