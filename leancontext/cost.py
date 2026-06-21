"""Cache-impact accounting — turn savings into a visible number.

Two honest facts we surface that the incumbent doesn't:
1. **$ saved**, computed from input-token price (input dominates agent cost).
2. **cache-safe = True**: because reductions are deterministic and content-addressed,
   a reduced block serialises to identical bytes every turn, so the provider
   prompt-cache prefix is preserved (we never bust the ~90% cache discount).

Prices change often, so the table is intentionally tiny and overridable. Pass an
explicit ``input_price_per_mtok`` or register prices with :func:`set_price`.
Unknown model + no price → token savings reported, ``usd_saved`` is ``None``.
"""

from __future__ import annotations

from typing import Optional

#: USD per 1M tokens (input, output). Indicative — override via set_price().
PRICING: dict[str, tuple[float, Optional[float]]] = {
    "claude-sonnet-4-6": (3.0, 15.0),  # verified 2026-06; others: register your own
}


def set_price(model: str, input_per_mtok: float, output_per_mtok: Optional[float] = None) -> None:
    PRICING[model] = (input_per_mtok, output_per_mtok)


def _input_price(model: Optional[str], override: Optional[float]) -> Optional[float]:
    if override is not None:
        return override
    if model:
        if model in PRICING:
            return PRICING[model][0]
        for key, (inp, _out) in PRICING.items():
            if model.startswith(key):
                return inp
    return None


def estimate_savings(reduction, model: Optional[str] = None,
                     input_price_per_mtok: Optional[float] = None) -> dict:
    """Estimate token + USD savings for a single reduction."""
    saved = max(0, reduction.tokens_before - reduction.tokens_after)
    price = _input_price(model, input_price_per_mtok)
    usd = None if price is None else round(saved / 1_000_000 * price, 6)
    return {
        "kind": reduction.kind,
        "tokens_before": reduction.tokens_before,
        "tokens_after": reduction.tokens_after,
        "tokens_saved": saved,
        "usd_saved": usd,
        "cache_safe": True,  # deterministic + content-addressed → prefix preserved
    }


class CostTracker:
    """Accumulate savings across many reductions. Install as a reduction hook.

        tracker = CostTracker(model="claude-sonnet-4-6").install()
        ... run your agent ...
        print(tracker.report())
    """

    def __init__(self, model: Optional[str] = None, input_price_per_mtok: Optional[float] = None):
        self.model = model
        self.price = input_price_per_mtok
        self.reductions = 0
        self.tokens_before = 0
        self.tokens_after = 0
        self.tokens_saved = 0
        self.usd_saved = 0.0
        self._has_price = False
        self._hook = None

    def _on(self, r) -> None:
        s = estimate_savings(r, self.model, self.price)
        self.reductions += 1
        self.tokens_before += s["tokens_before"]
        self.tokens_after += s["tokens_after"]
        self.tokens_saved += s["tokens_saved"]
        if s["usd_saved"] is not None:
            self.usd_saved += s["usd_saved"]
            self._has_price = True

    def install(self) -> "CostTracker":
        from .core import on_reduction
        self._hook = on_reduction(self._on)
        return self

    def uninstall(self) -> None:
        from .core import remove_reduction_hook
        if self._hook is not None:
            remove_reduction_hook(self._hook)
            self._hook = None

    def report(self) -> dict:
        ratio = 0.0 if self.tokens_before == 0 else 1.0 - self.tokens_after / self.tokens_before
        return {
            "reductions": self.reductions,
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
            "tokens_saved": self.tokens_saved,
            "ratio": round(ratio, 4),
            "usd_saved": round(self.usd_saved, 4) if self._has_price else None,
            "cache_safe": True,
        }
