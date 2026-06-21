<p align="center">
  <img src="assets/logo.svg" alt="LeanContext" width="440">
</p>

<p align="center">
  Cut the cost of AI agents by shrinking what they send to the model, without making the agent do less.
</p>

---

LeanContext reduces the bloated tool outputs (logs, JSON/RAG, diffs, stack traces, HTML) that agents re-send to the model every turn. It works at the source, where the content's type is still known. It stays deterministic, so it doesn't break the provider's prompt cache. It reports a fidelity score on every reduction. And it's fail-open: it can only help or no-op, never corrupt the agent's context.

> Status: early (v0). Apache-2.0. Python 3.10+. No required dependencies in the core path.

---

## Why

- The cost of agents is dominated by **input tokens**, not model output (often 10–50× more).
- A tool output added on turn *N* is **re-sent every later turn** — the quadratic tax.
- Those payloads are mostly redundancy: repeated timestamps, JSON keys, boilerplate, near-identical lines.

LeanContext keeps the signal (errors, anomalies, identifiers) and drops the redundancy.

```
incident log:  19,461 tokens  →  160 tokens   (99% saved, fidelity 100%, FATAL line preserved)
```

## Install

```bash
pip install -e .                 # core (stdlib only)
pip install -e ".[otel]"         # + OpenTelemetry metrics
pip install -e ".[tiktoken]"     # + exact token counts
pip install -e ".[integrations]" # + openai/anthropic/litellm/fastapi adapters
```

## Quickstart

```python
from leancontext import reduce

r = reduce(tool_output)     # type auto-detected
r.text                      # the lean string to send to the model
r.ratio, r.fidelity         # 0.97, 1.0
r.tokens_before, r.tokens_after
```

Three ways to integrate — pick your friction level (all share one core, all fail-open):

```python
import leancontext

# 1. decorator — one line per tool
@leancontext.reduce
def search_logs(q: str) -> str:
    ...

# 2. wrap all tools — one line, any framework (detects callables & tool objects)
tools = leancontext.wrap(tools)

# 3. wrap an SDK client — reduces tool outputs on the wire
client = leancontext.wrap(openai_client)        # or wrap_openai / wrap_anthropic
```

## Integrations

| Surface | How |
|---|---|
| Decorator / tools | `@leancontext.reduce`, `leancontext.wrap(tools)` |
| OpenAI / Anthropic / Gemini SDK | `wrap_openai(client)` / `wrap_anthropic(client)` / `wrap_gemini(client)` |
| LiteLLM (proxy) | `litellm_settings: callbacks: leancontext.integrations.litellm.proxy_handler_instance` |
| LiteLLM (SDK) | `import leancontext.integrations.litellm as ll; ll.patch()` |
| Standalone proxy | `from leancontext.integrations.proxy import create_app` (OpenAI-compatible, any language) |
| Wire/messages | `leancontext.reduce_messages(messages)` (OpenAI, Anthropic, Gemini formats) |
| OpenTelemetry | `import leancontext.integrations.otel as o; o.instrument()` |
| Anthropic native | `from leancontext.integrations.anthropic_native import wrap_anthropic_native` |

### Compose with Anthropic's native context editing (the differentiator)

LeanContext compresses *by content* on the way in; Anthropic's context editing clears old tool results *by age*. Run both together:

```python
from leancontext.integrations.anthropic_native import wrap_anthropic_native
client = wrap_anthropic_native(anthropic.Anthropic(),
                               trigger_input_tokens=30000, keep_tool_uses=3)
```

## Reducers

| Kind | What it does (deterministic, value-preserving) |
|---|---|
| `log` | Collapse near-identical lines; keep every error/anomaly/unique line verbatim |
| `json` | Factor repeated keys out once, values columnar (near-lossless) |
| `diff` | Keep all change/hunk/header lines; collapse unchanged context |
| `stacktrace` | Keep the exception + boundary frames; collapse the deep middle |
| `html` | Strip tags/scripts/styles; keep visible text + links |

Anything else, or any payload below thresholds → passed through unchanged.

## Measurable safety & cost

```python
from leancontext.cost import CostTracker
tracker = CostTracker(model="claude-sonnet-4-6").install()
# ... run your agent ...
tracker.report()   # {tokens_saved, usd_saved, ratio, cache_safe: True}
```

Every reduction carries a **fidelity** score (signal preserved); below threshold, the original is returned unchanged.

## Paging (flatten the quadratic)

```python
from leancontext import paging
ref_line = paging.page(big_old_tool_output, summary="1 FATAL")   # ~tens of tokens
paging.expand(ref_line)                                          # full original back
# expose paging.EXPAND_TOOL_SPEC to your agent so it can pull detail on demand
```

## Benchmark

```bash
python bench.py
```

## How it works

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the pipeline and integration diagrams. In short: hash → fail-open gates (disabled? too small? unknown type? reducer error? saving/fidelity below threshold?) → typed reducer → measured result. Reductions are deterministic and content-addressed, so the prompt-cache prefix stays stable.

## Configuration

```python
leancontext.disable()                  # global kill switch (or env LEANCONTEXT_DISABLED=1)
leancontext.reduce(x, min_saving=0.1, min_fidelity=0.85)
leancontext.on_reduction(cb)           # telemetry hook (composable)
leancontext.use_tiktoken("gpt-4o")     # exact token counts
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
