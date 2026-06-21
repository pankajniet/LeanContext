<p align="center">
  <img src="assets/logo.png" alt="LeanContext" width="460">
</p>

<p align="center">
  <b>Trim the tool output your AI agent re-sends every turn. Keep the signal, drop the noise.</b>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg"></a>
  <img alt="Python 3.14+" src="https://img.shields.io/badge/python-3.14%2B-blue.svg">
  <a href="https://github.com/pankajniet/LeanContext/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/pankajniet/LeanContext/actions/workflows/ci.yml/badge.svg"></a>
</p>

---

AI agents re-send every tool result (logs, JSON, diffs, stack traces, HTML) to the model on
every turn, and most of it is redundancy you pay for again and again. LeanContext sits between
your agent and the model and reduces those payloads to their signal: deterministically, with a
fidelity score on every reduction, and without ever breaking the agent.

```python
from leancontext import reduce

@reduce
def search_logs(query: str) -> str:
    return run_log_search(query)   # ~10k tokens of logs in, ~1k out, error lines kept
```

## See it

```text
$ python bench.py
sample              kind          before   after  saved  fidelity
-----------------------------------------------------------------
log (incident)      log            52642     100   100%      100%
json (RAG chunks)   json            1862    1390    25%      100%
html (web fetch)    html            1672    1093    35%      100%
diff (patch)        diff             639      81    87%      100%
stacktrace          stacktrace       896      94    90%      100%
-----------------------------------------------------------------
TOTAL                              57711    2758    95%
```

A real incident log, before and after:

```text
# before  (902 lines)
2026-06-21T09:00:01Z INFO  [gateway] req id=a1 path="/v1/render" status=200 ms=12
... 900 near-identical INFO lines ...
2026-06-21T09:10:43Z FATAL [render] OOM killed worker=7 doc="deck-8842" root cause

# after
2026-06-21T09:00:01Z INFO  [gateway] req id=a1 path="/v1/render" status=200 ms=12   ⟪×900 similar⟫
2026-06-21T09:10:43Z FATAL [render] OOM killed worker=7 doc="deck-8842" root cause
```

The redundant lines collapse to a count. The FATAL line that explains the crash is kept intact.

## Why it works

The model API is the bulk of an agent's cost, and most of that is *input* tokens. A tool result
added on one turn is re-sent on every later turn, so the bill grows with the length of the
conversation, not just the work done. Those payloads are mostly repetition. LeanContext keeps the
errors, anomalies, and identifiers, and collapses the rest.

## How it compares

|                                  | LeanContext | LLM-based compressor | Wire-level proxy |
| -------------------------------- | :---------: | :------------------: | :--------------: |
| No model in the reduction path   |      ✓      |          ✗           |      varies      |
| Deterministic                    |      ✓      |          ✗           |      varies      |
| Prompt-cache safe                |      ✓      |       often ✗        |     often ✗      |
| Type-aware (keeps error lines)   |      ✓      |          ✗           |        ✗         |
| Fidelity score per reduction     |      ✓      |          ✗           |        ✗         |
| Added latency / cost             |    none     |     a model call     |  a network hop   |

## Install

```bash
pip install -e .                  # core, standard library only
pip install -e ".[integrations]"  # openai, anthropic, litellm, fastapi adapters
pip install -e ".[otel]"          # OpenTelemetry metrics
pip install -e ".[tiktoken]"      # exact token counts (used automatically when present)
```

## Use it

Three levels, one core. Every path fails open: if anything goes wrong, you get the original text back.

```python
import leancontext

clean = leancontext.reduce(tool_output).text     # 1) manual

@leancontext.reduce                              # 2) decorator, one line per tool
def search_logs(q: str) -> str:
    ...

tools  = leancontext.wrap(tools)                 # 3) wrap all tools, or an SDK client
client = leancontext.wrap(openai_client)         #    (wrap_anthropic / wrap_gemini too)
```

Every reduction is inspectable:

```python
r = leancontext.reduce(tool_output)
r.text                            # what to send to the model
r.tokens_before, r.tokens_after
r.ratio                           # fraction saved
r.fidelity                        # 0..1 signal preserved
```

## Integrations

| Surface | How |
| --- | --- |
| Decorator / tools | `@leancontext.reduce`, `leancontext.wrap(tools)` |
| OpenAI / Anthropic / Gemini SDK | `wrap_openai(c)`, `wrap_anthropic(c)`, `wrap_gemini(c)` |
| LiteLLM (proxy) | `callbacks: leancontext.integrations.litellm.proxy_handler_instance` |
| LiteLLM (SDK) | `import leancontext.integrations.litellm as ll; ll.patch()` |
| Standalone proxy | `from leancontext.integrations.proxy import create_app` (OpenAI-compatible, any language) |
| Messages | `leancontext.reduce_messages(messages)` (OpenAI, Anthropic, Gemini) |
| Telemetry | `import leancontext.integrations.otel as o; o.instrument()` |
| Anthropic native | `wrap_anthropic_native(client, ...)` composes with `clear_tool_uses` context editing |

## Reducers

| Kind | What it does |
| --- | --- |
| `log` | Collapse near-identical lines, keep every error, anomaly, and unique line verbatim |
| `json` | Factor repeated keys out once, lay values out columnar (near-lossless) |
| `diff` | Keep all change, hunk, and header lines, collapse unchanged context |
| `stacktrace` | Keep the exception and boundary frames, collapse the deep middle |
| `html` | Strip tags, scripts, and styles, keep visible text and links |

Anything else, or any payload below the size, saving, or fidelity thresholds, passes through unchanged.

## How it works

Each tool output flows through fail-open gates (hash, size check, type detection, the typed
reducer, then a saving and fidelity check) and returns either the reduced text or the original.
Results are cached by content hash, so a payload re-sent across turns is reduced only once.
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for diagrams.

## Cost and telemetry

```python
from leancontext.cost import CostTracker

tracker = CostTracker(model="claude-sonnet-4-6").install()
# ... run your agent ...
tracker.report()    # {tokens_saved, usd_saved, ratio, cache_safe: True}
```

## Configuration

```python
leancontext.disable()                         # global kill switch (or env LEANCONTEXT_DISABLED=1)
leancontext.reduce(x, min_saving=0.1, min_fidelity=0.85)
leancontext.on_reduction(callback)            # telemetry hook (composable)
leancontext.use_tiktoken("gpt-4o")            # force a specific model's tokenizer
```

## Roadmap

Accurate provider tokenizers by default, an MCP server, tested LangChain / LlamaIndex / CrewAI
adapters, broader Anthropic native interop, and a PyPI release.

## Contributing

Issues and PRs welcome. Run `pytest`. Reducers are pure functions, `str -> (reduced, notes)`,
and must be deterministic and value-preserving. See [AGENTS.md](AGENTS.md) for the design rules.

## License

[Apache-2.0](LICENSE)
