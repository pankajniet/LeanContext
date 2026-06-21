"""Cost accounting: turn token savings into dollars.

Reports two things:
1. Dollars saved, from the input-token price (input dominates agent cost).
2. ``cache_safe = True``: reductions are deterministic and content-addressed, so a
   reduced block serialises to the same bytes every turn and the provider's
   prompt-cache prefix stays intact.

Prices change often, so the built-in table is small and overridable: pass an
explicit ``input_price_per_mtok`` or register prices with :func:`set_price`. With
no known price, token savings are still reported and ``usd_saved`` is ``None``.
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
    saved = reduction.tokens_saved
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
        self.has_price = _input_price(model, input_price_per_mtok) is not None
        self._hook = None

    def _on(self, r) -> None:
        self.reductions += 1
        self.tokens_before += r.tokens_before
        self.tokens_after += r.tokens_after
        self.tokens_saved += r.tokens_saved
        if self.has_price:
            self.usd_saved += estimate_savings(r, self.model, self.price)["usd_saved"]

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
            "usd_saved": round(self.usd_saved, 4) if self.has_price else None,
            "cache_safe": True,
        }
