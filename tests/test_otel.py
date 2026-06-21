import pytest

import leancontext


def _log(n=400):
    lines = [f"2026-06-21T09:00:{i % 60:02d}.000Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(200, "2026-06-21T09:05:00.000Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


@pytest.fixture(autouse=True)
def _clean_hooks():
    leancontext.clear_reduction_hooks()
    yield
    leancontext.clear_reduction_hooks()


def test_multiple_hooks_compose_and_remove():
    seen = []
    h1 = leancontext.on_reduction(lambda r: seen.append(("a", r.kind)))
    leancontext.on_reduction(lambda r: seen.append(("b", r.kind)))

    leancontext.reduce(_log())
    assert ("a", "log") in seen and ("b", "log") in seen   # both hooks fired

    seen.clear()
    leancontext.remove_reduction_hook(h1)
    leancontext.reduce(_log())
    assert ("a", "log") not in seen and ("b", "log") in seen  # only h1 removed


def test_hook_exception_never_breaks_reduction():
    leancontext.on_reduction(lambda r: 1 / 0)        # misbehaving telemetry
    r = leancontext.reduce(_log())
    assert r.kind == "log" and "root cause" in r.text  # reduction still succeeds


def test_passthrough_does_not_emit():
    seen = []
    leancontext.on_reduction(lambda r: seen.append(r.kind))
    leancontext.reduce("short string")               # below min_tokens -> passthrough
    assert seen == []                                # only applied reductions emit


def test_otel_metrics_recorded_live():
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    import leancontext.integrations.otel as lc_otel

    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    lc_otel.instrument(meter_provider=provider)
    try:
        leancontext.reduce(_log())
        data = reader.get_metrics_data()
        names = {
            m.name
            for rm in data.resource_metrics
            for sm in rm.scope_metrics
            for m in sm.metrics
        }
    finally:
        lc_otel.uninstrument()

    assert "leancontext.tokens.saved" in names
    assert "leancontext.reduction.ratio" in names
    assert "leancontext.reduction.fidelity" in names
