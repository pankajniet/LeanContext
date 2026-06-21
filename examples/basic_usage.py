"""Minimal LeanContext examples. Run: python examples/basic_usage.py"""

import leancontext
from leancontext.cost import CostTracker


def make_log(n=600):
    lines = [f"2026-06-21T09:00:{i % 60:02d}Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(300, "2026-06-21T09:05:00Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


def example_manual():
    r = leancontext.reduce(make_log())
    print(f"manual:    {r.tokens_before} -> {r.tokens_after} tokens "
          f"({r.ratio:.0%} saved, fidelity {r.fidelity:.0%})")
    assert "root cause" in r.text          # the signal survives


def example_decorator():
    @leancontext.reduce
    def search_logs(query: str) -> str:
        return make_log()

    out = search_logs("errors")            # returns a plain str, already reduced
    print(f"decorator: tool returned {len(out)} chars (reduced)")


def example_cost_tracking():
    tracker = CostTracker(input_price_per_mtok=3.0).install()
    try:
        for _ in range(5):                 # same output 5 turns: reduced once, counted each time
            leancontext.reduce(make_log())
    finally:
        tracker.uninstall()
    print(f"cost:      {tracker.report()}")


if __name__ == "__main__":
    example_manual()
    example_decorator()
    example_cost_tracking()
