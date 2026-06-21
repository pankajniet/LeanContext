# AGENTS.md — LeanContext

> Project name: **LeanContext** — keep agent context lean (drop redundant boilerplate, keep the signal). Easy to rename.
> This file is the contract for any human or AI agent working in this repo. Read it before writing code.

## 1. Mission

Cut the cost of agentic LLM workflows by shrinking **what we send to the model**, without
making the agent do less. The cost driver is *input tokens* — tool outputs, log dumps, RAG
chunks, and JSON responses that arrive raw (repeated keys, boilerplate, verbose formatting)
and are then **re-sent on every turn** (the quadratic tax).

We reduce that payload **at the source** — the moment a tool result is produced — where its
structure is still known. Deterministic, type-aware, cache-stable, and with **measurable
fidelity** so teams can trust it in production.

**Three pillars (our verified edge vs the incumbent Headroom — see §11):**
1. **Cache-safe by construction** — deterministic + content-addressed, so we never break the
   provider prompt-cache discount (Headroom's cache benefit is conditional).
2. **Measurable fidelity** — a safety score on *every* reduction, not just dataset-level aggregates.
3. **Provider-native interop** — composes with Anthropic context-editing / compaction / memory tool
   and LiteLLM, instead of replacing them. Zero ML in the path (no overhead, no language bias).

## 2. The problem (settled)

- The cost is the **input**, not the model output (input is typically 10–50× output in coding agents).
- A tool output added on turn N is paid for again on every later turn → **O(n²)**.
- Raw payloads are mostly redundancy: repeated timestamps, JSON keys, boilerplate, near-identical lines.

## 3. Why existing "compress-on-the-wire" middleware falls short

These are the gaps LeanContext is designed to beat. Do not reintroduce them.

| Gap | Their failure | Our fix |
|-----|---------------|---------|
| Structure-blind | Compresses a flattened request blob; can't tell a log from RAG | Reduce at the **tool-result boundary**, type-aware |
| Still O(n²) | Compresses but re-sends every turn | Optional **paging**: aged results → expandable refs (O(1)) |
| Breaks prompt caching | Non-deterministic / cross-context compression busts the prefix cache | **Deterministic + content-addressed** → cache-stable |
| Reversibility helps humans, not the agent | Model only sees compressed text, can't ask for detail | Paging gives the agent an `expand` handle |
| No measurable safety | "usually keeps the signal" is a probability | **Fidelity score** per reduction |
| Re-compress churn | Re-runs every turn | Reduce **once**, cache by content hash |
| Value loss | Drops an exact ID/number the agent needed | **Value-preserving** reducers |

## 4. Design principles (non-negotiable)

1. **Reduce at the source, not the wire.** Structure = safety + ratio.
2. **No LLM in the reduction path.** Deterministic, microsecond-scale, debuggable, free.
3. **Deterministic & content-addressed.** Same input → same output → stays cacheable.
4. **Anomaly-preserving.** The rare line *is* the signal. Frequency-1 patterns and
   error/warn/exception lines are kept verbatim.
5. **Value-preserving.** Never silently drop identifiers, numbers, paths, or quoted values
   that could be load-bearing for the agent's reasoning.
6. **Measurable safety.** Every reduction reports a fidelity score and what it preserved/dropped.
7. **Non-invasive by default.** `@reduce` decorator / tool wrapper. Paging is opt-in.
8. **Honest accounting.** Report tokens before/after *and* cache-aware cost estimate.

## 5. Integration & adoption (the make-or-break)

Adoption dies on two things: **friction** and **fear**. These rules kill both.

**A. Tiered integration — pick your friction level. All routes share one core.**
1. Manual: `reduce(text).text` — zero coupling, works literally anywhere.
2. Decorator: `@reduce` on a tool function — one line per tool.
3. Bulk wrap: `tools = leancontext.wrap(tools)` — one line for all tools; detects LangChain/OpenAI/CrewAI tool objects and plain callables.
4. Client fallback: `client = leancontext.wrap(openai_client)` — when you can't touch the tools (structure-blind, last resort).

**B. Target the tool *callable*, not the framework.** Every framework ultimately invokes a Python
callable for a tool. Operating on the callable's return value is universal — no per-framework code.

**C. Fail open, ALWAYS.** Never break the agent. If the type is unknown, the reducer errors, the
saving is below threshold, or fidelity is below threshold → return the **original, unchanged**.
LeanContext can only ever help or no-op. This is the single most important rule.

**D. Preserve the tool contract.** Same signature, same return type (`str` in → `str` out).
The agent never knows LeanContext exists. No new required params, no behavior change.

**E. Zero config, sane defaults.** `pip install leancontext`, add one line. No setup, no keys, no service.

**F. Global kill switch.** `LEANCONTEXT_DISABLED=1` (env) or `leancontext.disable()` instantly no-ops
everything — the trust lever teams need during an incident.

**G. Silent by default, observable on demand.** No logging unless a hook is attached
(`leancontext.on_reduction(cb)` for savings telemetry). Never spams stdout.

**H. No forced dependencies.** Core is stdlib-only. Real tokenizers (tiktoken) and framework
adapters are optional extras.

## 6. Non-goals

- Not a hosted service or dashboard. Local-first, library-first.
- Not a model router or gateway (compose with LiteLLM etc., don't replace them).
- Not lossy "summarization by an LLM" (that costs tokens to save tokens, and is non-deterministic).
- Not a memory framework (compose with the agent's own history management).

## 7. Architecture

```
leancontext/
  __init__.py        # public API: reduce(), Reduction, reduce decorator
  core.py            # dispatch, type detection, Reduction dataclass, token counting
  fidelity.py        # salience extraction + fidelity scoring
  tokens.py          # pluggable token counter (heuristic default, optional tiktoken)
  reducers/
    __init__.py
    logs.py          # collapse near-identical lines, keep anomalies/errors verbatim
    json_data.py     # factor schema once, send rows as values (columnar)
    diff.py          # keep changed hunks, reference unchanged   (later)
    stacktrace.py    # keep frames at the boundary + the cause   (later)
  integrations/
    decorator.py     # @reduce for tool functions
    client.py        # provider client wrapper (fallback surface) (later)
```

Public API (stable target):

```python
from leancontext import reduce

r = reduce(tool_output)            # kind auto-detected
r.text                             # reduced string to send to the model
r.tokens_before, r.tokens_after    # honest accounting
r.ratio                            # 0.0–1.0 saved
r.fidelity                         # 0.0–1.0 signal preserved
r.kind, r.notes, r.ref             # type, human notes, content hash (for paging)
```

```python
from leancontext import reduce as reduce_tool

@reduce_tool                       # non-invasive integration
def search_logs(query: str) -> str:
    ...
```

## 8. Conventions

- Python 3.10+. Standard library only in the core path; optional extras (tiktoken) behind a flag.
- Type hints everywhere. Dataclasses for results.
- Pure functions for reducers: `reduce(text, **opts) -> Reduction`. No global state, no I/O.
- Determinism is a test requirement: same input must yield byte-identical output.
- Every reducer ships with: a fidelity guarantee, a docstring stating what it preserves, and tests.

## 9. Testing

- `pytest`. Each reducer: ratio test (achieves target on representative input), determinism test,
  and a fidelity test (known salient tokens survive).
- A golden "incident log" fixture is the canonical demo: a ~10k-token log with one FATAL line
  must reduce hard while preserving the FATAL line and all distinct error templates.

## 10. Roadmap

- **v0 (now):** core dispatch + `logs` + `json_data` reducers, fidelity, token accounting, `@reduce`, demo.
- **v0.1:** `diff`, `stacktrace`, `table`, `html` reducers; tiktoken integration; CLI (`leancontext reduce <file>`).
- **v0.2:** opt-in paging tier (`expand` tool + content store); client-wrapper fallback surface.
- **v0.3:** framework adapters (LangChain/LlamaIndex/CrewAI tool wrappers); cost report.

## 11. Differentiation — evidence-based (vs Headroom, verified 2026-06-21)

Headroom (github.com/chopratejas/headroom, Apache-2.0, v0.26.0) is the reference incumbent and is
genuinely strong: library + proxy + MCP + CCR reversible retrieval, hybrid statistical+ML compression.

**Non-clone rule (crucial):** we do NOT re-implement Headroom. Where it is strong (Rust "SmartCrusher"
statistical JSON, AST-aware code compaction, ML "Kompress"), we either match with a *standard*
(e.g. TOON for structured data, later) or defer. We compete ONLY on its **verified gaps** below.

| Verified gap in Headroom | LeanContext's edge |
|---|---|
| No interop with provider-native context mgmt (Anthropic `clear_tool_uses` / compaction / memory tool) | Compose with them: compress on ingest, provider clears on age. Cross-provider. |
| No per-reduction fidelity score (only dataset-level aggregates) | Fidelity score on every reduction; fail-open below threshold. |
| Prompt-cache benefit is conditional (changing prefixes erase KV-cache savings) | Cache-safe by construction: deterministic, per-block, content-addressed → reduce once, stable bytes. |
| Hybrid uses ML (Kompress): overhead, English-biased, net-negative on fast models | Zero-ML, deterministic → no model load, no language bias, never net-negative. |
| RAG document text + small/under-threshold payloads pass through | (Roadmap) optionally reduce RAG document blocks safely. |
| Reversibility bounded by TTL + local LRU (RAM cost) | Determinism lets us re-derive instead of store; lighter retrieval. |

