"""Measure real token and cost savings with prompt caching ON.

This runs a short multi-turn conversation twice against a live model: once
sending raw tool outputs, once with LeanContext reducing them. Prompt caching is
enabled in both runs, so the numbers reflect the *marginal* saving on top of what
caching already does. Totals come from the API's own usage fields, not estimates.

It auto-selects the provider from whichever key is set:

    # Anthropic (explicit cache telemetry)
    pip install anthropic && export ANTHROPIC_API_KEY=...

    # or OpenAI (automatic prompt caching)
    pip install openai && export OPENAI_API_KEY=...

    python examples/validate_caching.py

Optional env: LEANCONTEXT_VALIDATE_MODEL, LEANCONTEXT_VALIDATE_TURNS.
Nothing here touches the network until you run it with a key.
"""

from __future__ import annotations

import os

import leancontext

TURNS = int(os.environ.get("LEANCONTEXT_VALIDATE_TURNS", "6"))

# USD per 1M tokens. Anthropic: cache write = 1.25x input, read = 0.1x input.
PRICE_ANTHROPIC = {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.30}
# OpenAI: cached input is billed at a discount.
PRICE_OPENAI = {"input": 2.5, "cached": 1.25, "output": 10.0}


def make_log(turn: int, n: int = 400) -> str:
    lines = [
        f"2026-06-21T09:{turn:02d}:{i % 60:02d}Z INFO [worker] job={i} status=ok ms={i % 50}"
        for i in range(n)
    ]
    lines.insert(200, f"2026-06-21T09:{turn:02d}:30Z FATAL [render] OOM killed worker={turn} — root cause")
    return "\n".join(lines)


def _prompt(turn: int, reduce: bool) -> str:
    log = leancontext.reduce(make_log(turn)).text if reduce else make_log(turn)
    return f"Tool output (turn {turn}):\n{log}\n\nIn one short line, what is the key error in turn {turn}?"


# --- Anthropic ---------------------------------------------------------------

def run_anthropic(client, model: str, *, reduce: bool) -> dict:
    messages: list[dict] = []
    totals = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    for turn in range(TURNS):
        messages.append({"role": "user", "content": [
            {"type": "text", "text": _prompt(turn, reduce), "cache_control": {"type": "ephemeral"}},
        ]})
        usage = client.messages.create(model=model, max_tokens=64, messages=messages).usage
        totals["input"] += getattr(usage, "input_tokens", 0)
        totals["output"] += getattr(usage, "output_tokens", 0)
        totals["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0
        totals["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
        messages.append({"role": "assistant", "content": "ok"})
    return totals


def cost_anthropic(t: dict) -> float:
    p = PRICE_ANTHROPIC
    return (t["input"] * p["input"] + t["output"] * p["output"]
            + t["cache_write"] * p["cache_write"] + t["cache_read"] * p["cache_read"]) / 1_000_000


# --- OpenAI ------------------------------------------------------------------

def run_openai(client, model: str, *, reduce: bool) -> dict:
    messages: list[dict] = []
    totals = {"input": 0, "output": 0, "cached": 0}
    for turn in range(TURNS):
        messages.append({"role": "user", "content": _prompt(turn, reduce)})
        resp = client.chat.completions.create(model=model, max_tokens=64, messages=messages)
        usage = resp.usage
        totals["input"] += usage.prompt_tokens
        totals["output"] += usage.completion_tokens
        details = getattr(usage, "prompt_tokens_details", None)
        totals["cached"] += getattr(details, "cached_tokens", 0) or 0
        messages.append({"role": "assistant", "content": resp.choices[0].message.content or "ok"})
    return totals


def cost_openai(t: dict) -> float:
    p = PRICE_OPENAI
    uncached = max(0, t["input"] - t["cached"])
    return (uncached * p["input"] + t["cached"] * p["cached"] + t["output"] * p["output"]) / 1_000_000


# --- driver ------------------------------------------------------------------

def _report(baseline: dict, lean: dict, cost_fn, turns: int) -> None:
    base_cost, lean_cost = cost_fn(baseline), cost_fn(lean)
    print(f"{'baseline':<12} {baseline}   ${base_cost:.4f}")
    print(f"{'leancontext':<12} {lean}   ${lean_cost:.4f}")
    saved = 0.0 if base_cost == 0 else 1 - lean_cost / base_cost
    print(f"\nMeasured cost saving with caching ON: {saved:.0%}  "
          f"(${base_cost - lean_cost:.4f} over {turns} turns)")


def main() -> int:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
        except ImportError:
            print("Install the SDK first:  pip install anthropic")
            return 1
        model = os.environ.get("LEANCONTEXT_VALIDATE_MODEL", "claude-sonnet-4-6")
        client = anthropic.Anthropic()
        print(f"Provider: Anthropic | model: {model} | turns: {TURNS} | caching: on\n")
        _report(run_anthropic(client, model, reduce=False),
                run_anthropic(client, model, reduce=True), cost_anthropic, TURNS)
        return 0

    if os.environ.get("OPENAI_API_KEY"):
        try:
            import openai
        except ImportError:
            print("Install the SDK first:  pip install openai")
            return 1
        model = os.environ.get("LEANCONTEXT_VALIDATE_MODEL", "gpt-4o")
        client = openai.OpenAI()
        print(f"Provider: OpenAI | model: {model} | turns: {TURNS} | caching: automatic\n")
        _report(run_openai(client, model, reduce=False),
                run_openai(client, model, reduce=True), cost_openai, TURNS)
        return 0

    print("Set ANTHROPIC_API_KEY or OPENAI_API_KEY to run this (it makes live API calls).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
