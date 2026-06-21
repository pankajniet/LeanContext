# LeanContext — How it works

LeanContext reduces what an agent sends to the model by shrinking **tool outputs at the source**,
deterministically and type-aware, with a fidelity score on every reduction. It can only ever
**help or no-op** — never corrupt the agent's context.

---

## 1. The problem: the quadratic tax

A tool output added on turn *N* is re-sent on every later turn. A 10k-token log in a 30-turn
session costs ~10k × 27 ≈ **270k tokens** — the bill is dominated by *re-sent* context.

```mermaid
flowchart LR
    subgraph Without["Without LeanContext  (O(n²))"]
      A1[Turn 3: 10k log] --> A2[Turn 4: 10k re-sent]
      A2 --> A3[Turn 5: 10k re-sent] --> A4[... Turn 30: 10k re-sent]
    end
    subgraph With["With LeanContext"]
      B1[Turn 3: reduce once → 160] --> B2[Turn 4: 160, cache HIT]
      B2 --> B3[Turn 5: 160, cache HIT] --> B4[... Turn 30: 160, cache HIT]
    end
```

---

## 2. The reduce() pipeline (the heart)

Every non-happy branch returns the **original text unchanged** (fail-open). Reductions are
deterministic and content-addressed, so the same input always yields the same bytes — which keeps
the provider prompt-cache hitting.

```mermaid
flowchart TD
    A[Tool output] --> B["reduce(content)"]
    B --> R[hash content → ref]
    R --> C{disabled?<br/>or &lt; 50 tokens?}
    C -- yes --> P[[return ORIGINAL<br/>kind = passthrough]]
    C -- no --> D[detect_kind:<br/>log / json / text]
    D --> E{reducer exists<br/>for kind?}
    E -- no --> P
    E -- yes --> F["run typed reducer (try/except)<br/>anomaly-preserving + value-preserving"]
    F -- raises --> P
    F -- ok --> G[measure tokens_after<br/>+ fidelity score]
    G --> H{saving ≥ 10%<br/>AND fidelity ≥ 85%?}
    H -- no --> P
    H -- yes --> I[[return REDUCED<br/>+ emit telemetry hook]]
```

**Typed reducers**
- **logs** — mask volatile parts (timestamps, ids, numbers) → group identical templates → keep one
  representative + a count; error/anomaly/unique lines kept verbatim.
- **json** — factor repeated keys out once, emit values columnar (near-lossless).

---

## 3. Two integration surfaces, one core

```mermaid
flowchart TD
    subgraph SourceA["Surface A — at the source (preferred)"]
      T1["@reduce def tool() -> str"] --> T2[tool runs] --> T3["reduce()"] --> T4[lean string → history]
    end
    subgraph GatewayB["Surface B — at the gateway (zero code change)"]
      G1[Agent/framework assembles messages] --> G2[LiteLLM async_pre_call_hook]
      G2 --> G3["reduce_messages()<br/>only role:tool / tool_result blocks"] --> G4[LLM]
    end
    T3 -. same pipeline .-> CORE[(reduce pipeline)]
    G3 -. same pipeline .-> CORE
```

- **Surface A** knows the content type at birth → safest, highest ratio. (`@reduce`, `wrap(tools)`)
- **Surface B** captures agents you can't modify, any language. (LiteLLM proxy/SDK)
- Instructions (system/user/assistant) are **never** touched — only tool results.

---

## 4. The full vision (v0.2+): paging + provider-native interop

```mermaid
flowchart TD
    O[Tool output] --> RED["reduce() — fresh turn"]
    RED --> LEAN[lean, typed, cache-stable → model]
    RED --> STORE[(store original by ref)]
    STORE --> AGE["aged: agent moved on"]
    AGE --> PAGE["paging tier → 'log_ref://a1b2 (1 FATAL…)' ~25 tokens, expandable"]
    PAGE --> MODEL2[→ model]
    LEAN --> INTEROP
    PAGE --> INTEROP
    subgraph INTEROP["composes with — does not replace"]
      direction LR
      X[Anthropic context-editing<br/>clear_tool_uses → clears by AGE]
      Y[LeanContext<br/>shrinks by CONTENT]
    end
```

LeanContext shrinks **by content** on ingest; Anthropic context-editing clears **by age**. They run
together — cross-provider, deterministic, measurable.
