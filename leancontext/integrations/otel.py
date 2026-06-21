"""OpenTelemetry integration — emit reduction savings as standard telemetry.

Follows the OpenTelemetry GenAI semantic-conventions posture (converged industry
standard as of early 2026): emit **metrics** for token usage/savings, and attach a
**content-free span event** to the active span if one is recording. We never put
payload content in attributes (that is the documented anti-pattern — size/PII).

Import-safe: ``opentelemetry`` is imported lazily inside ``instrument`` only, so it
stays an optional dependency (``pip install leancontext[otel]``).

Usage::

    import leancontext.integrations.otel as lc_otel
    lc_otel.instrument()            # uses the global MeterProvider/TracerProvider
"""

from __future__ import annotations

from typing import Any

from ..core import on_reduction, remove_reduction_hook

_INSTALLED: dict[str, Any] = {}


def instrument(meter_provider: Any = None) -> Any:
    """Register a reduction hook that records OTel metrics + span events. Idempotent."""
    if "hook" in _INSTALLED:
        return _INSTALLED["hook"]

    from opentelemetry import metrics, trace

    meter = metrics.get_meter("leancontext", meter_provider=meter_provider)

    m_before = meter.create_counter("leancontext.tokens.before", unit="token",
                                    description="Input tokens before reduction")
    m_after = meter.create_counter("leancontext.tokens.after", unit="token",
                                   description="Input tokens after reduction")
    m_saved = meter.create_counter("leancontext.tokens.saved", unit="token",
                                   description="Input tokens saved by reduction")
    m_count = meter.create_counter("leancontext.reductions", unit="1",
                                   description="Number of applied reductions")
    h_ratio = meter.create_histogram("leancontext.reduction.ratio", unit="1",
                                     description="Fraction of tokens saved (0..1)")
    h_fidelity = meter.create_histogram("leancontext.reduction.fidelity", unit="1",
                                        description="Signal preserved (0..1)")

    def _hook(r) -> None:
        attrs = {"leancontext.kind": r.kind}
        saved = r.tokens_saved
        m_before.add(r.tokens_before, attrs)
        m_after.add(r.tokens_after, attrs)
        m_saved.add(saved, attrs)
        m_count.add(1, attrs)
        h_ratio.record(r.ratio, attrs)
        h_fidelity.record(r.fidelity, attrs)

        span = trace.get_current_span()
        if span is not None and span.is_recording():
            # Metadata only — never the payload (GenAI semconv: no content in attributes).
            span.add_event("leancontext.reduction", {
                "leancontext.kind": r.kind,
                "gen_ai.usage.input_tokens.before": r.tokens_before,
                "gen_ai.usage.input_tokens.after": r.tokens_after,
                "leancontext.tokens.saved": saved,
                "leancontext.reduction.ratio": r.ratio,
                "leancontext.reduction.fidelity": r.fidelity,
            })

    on_reduction(_hook)
    _INSTALLED["hook"] = _hook
    return _hook


def uninstrument() -> None:
    hook = _INSTALLED.pop("hook", None)
    if hook is not None:
        remove_reduction_hook(hook)
