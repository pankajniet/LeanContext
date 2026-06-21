"""Before/after benchmark over representative agent tool outputs.

Run:  python bench.py
"""

from __future__ import annotations

import leancontext
from leancontext.cost import estimate_savings


def _log(n=900):
    out = []
    for i in range(n):
        rid = f"{i:08x}-1c2d-4e5f-8a9b-0011223344{i % 100:02d}"
        ts = f"2026-06-21T09:{(i // 60) % 60:02d}:{i % 60:02d}.{i % 1000:03d}Z"
        out.append(f'{ts} INFO [gateway] req id={rid} path="/v1/render" status=200 ms={i % 80}')
    out.insert(640, '2026-06-21T09:10:43Z FATAL [render] OOM killed worker=7 doc="deck-8842" — root cause')
    return "\n".join(out)


def _json(n=60):
    rows = ",".join(
        f'{{"id":"chunk-{i}","source":"docs/guide.md","score":0.{90 - i % 90},'
        f'"text":"Section {i} explains server-side slide rendering."}}'
        for i in range(n)
    )
    return "[" + rows + "]"


def _html(n=120):
    items = "".join(f"<li>Result {i}: server-side rendering note</li>" for i in range(n))
    return ("<!doctype html><html><head><style>.x{color:red}</style>"
            "<script>var a=1;" + ("x" * 400) + "</script></head><body>"
            "<h1>Search Results</h1><ul>" + items + "</ul>"
            "<a href='https://example.com/more'>more</a></body></html>")


def _diff(n=60):
    ctx = "\n".join(f" unchanged line {i}" for i in range(n))
    return ("diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
            f"@@ -1,{n} +1,{n} @@\n" + ctx + "\n-    return None\n+    return result\n" + ctx)


def _trace(n=40):
    frames = "\n".join(
        f'  File "module_{i}.py", line {i*7}, in handler_{i}\n    step_{i}()' for i in range(n)
    )
    return "Traceback (most recent call last):\n" + frames + "\nRuntimeError: pipeline stalled — root cause"


SAMPLES = {
    "log (incident)": _log(),
    "json (RAG chunks)": _json(),
    "html (web fetch)": _html(),
    "diff (patch)": _diff(),
    "stacktrace": _trace(),
}

PRICE_PER_MTOK = 3.0  # USD/1M input tokens (e.g. Claude Sonnet 4.6)


def main() -> None:
    print(f"{'sample':<20}{'kind':<12}{'before':>8}{'after':>8}{'saved':>7}{'fidelity':>10}")
    print("-" * 65)
    tot_before = tot_after = 0
    usd = 0.0
    for name, payload in SAMPLES.items():
        r = leancontext.reduce(payload)
        tot_before += r.tokens_before
        tot_after += r.tokens_after
        usd += estimate_savings(r, input_price_per_mtok=PRICE_PER_MTOK)["usd_saved"]
        print(f"{name:<20}{r.kind:<12}{r.tokens_before:>8}{r.tokens_after:>8}"
              f"{r.ratio:>6.0%}{r.fidelity:>10.0%}")
    print("-" * 65)
    ratio = 1 - tot_after / tot_before if tot_before else 0
    print(f"{'TOTAL':<32}{tot_before:>8}{tot_after:>8}{ratio:>6.0%}")
    print(f"\nEstimated input-token cost saved (once, @ ${PRICE_PER_MTOK}/M): ${usd:.4f}")
    print("Re-sent every turn in a real loop, so multiply by turns held in context.")
    print("All reductions are deterministic → prompt-cache prefix preserved (cache-safe).")


if __name__ == "__main__":
    main()
