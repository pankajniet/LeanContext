import pytest

import leancontext


def _big_log(n=300):
    lines = [f"2026-06-21T09:00:{i % 60:02d}.000Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(150, "2026-06-21T09:05:00.000Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


# --- Anthropic provider-native interop ---------------------------------------

def test_context_management_schema_matches_api():
    from leancontext.integrations.anthropic_native import context_management

    cm = context_management(
        trigger_input_tokens=30000, keep_tool_uses=3,
        clear_at_least_input_tokens=5000, exclude_tools=["web_search"], clear_tool_inputs=False,
    )
    edit = cm["edits"][0]
    assert edit["type"] == "clear_tool_uses_20250919"
    assert edit["trigger"] == {"type": "input_tokens", "value": 30000}
    assert edit["keep"] == {"type": "tool_uses", "value": 3}
    assert edit["clear_at_least"] == {"type": "input_tokens", "value": 5000}
    assert edit["exclude_tools"] == ["web_search"]
    assert edit["clear_tool_inputs"] is False


def test_context_management_minimal_defaults():
    from leancontext.integrations.anthropic_native import context_management
    assert context_management() == {"edits": [{"type": "clear_tool_uses_20250919"}]}


def test_wrap_anthropic_native_composes_reduction_and_clearing():
    anthropic = pytest.importorskip("anthropic")
    from leancontext.integrations.anthropic_native import BETA_HEADER, wrap_anthropic_native

    client = anthropic.Anthropic(api_key="test-key")
    captured = {}
    client.messages.create = lambda **kw: captured.update(kw) or "OK"

    wrap_anthropic_native(client, trigger_input_tokens=30000, keep_tool_uses=3)
    client.messages.create(
        model="claude-opus-4-8", max_tokens=16,
        messages=[{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": _big_log()},
        ]}],
    )
    # native clearing enabled
    assert captured["context_management"]["edits"][0]["type"] == "clear_tool_uses_20250919"
    assert captured["context_management"]["edits"][0]["trigger"]["value"] == 30000
    assert captured["extra_headers"]["anthropic-beta"] == BETA_HEADER
    # our content reduction also applied
    sent = captured["messages"][0]["content"][0]["content"]
    assert len(sent) < len(_big_log()) and "root cause" in sent


# --- cache-impact accounting -------------------------------------------------

def test_estimate_savings_with_price():
    from leancontext.cost import estimate_savings
    r = leancontext.reduce(_big_log())
    s = estimate_savings(r, input_price_per_mtok=3.0)
    assert s["tokens_saved"] > 0
    assert s["usd_saved"] > 0
    assert s["cache_safe"] is True


def test_estimate_unknown_model_usd_none():
    from leancontext.cost import estimate_savings
    r = leancontext.reduce(_big_log())
    s = estimate_savings(r, model="some-unknown-model")
    assert s["usd_saved"] is None and s["tokens_saved"] > 0


def test_cost_tracker_accumulates():
    from leancontext.cost import CostTracker

    leancontext.clear_reduction_hooks()
    tracker = CostTracker(input_price_per_mtok=3.0).install()
    try:
        leancontext.reduce(_big_log())
        leancontext.reduce(_big_log())
        rep = tracker.report()
    finally:
        tracker.uninstall()

    assert rep["reductions"] == 2
    assert rep["tokens_saved"] > 0
    assert rep["usd_saved"] > 0
    assert rep["cache_safe"] is True
