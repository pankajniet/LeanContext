import asyncio

import pytest


def _big_log(n=300):
    lines = [f"2026-06-21T09:00:{i % 60:02d}.000Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(150, "2026-06-21T09:05:00.000Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


def _openai_tool_msg():
    return {"role": "tool", "tool_call_id": "c1", "content": _big_log()}


def _anthropic_msg():
    return {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": _big_log()},
    ]}


# --- real SDK client wrappers ------------------------------------------------

def test_wrap_openai_client_reduces_messages():
    openai = pytest.importorskip("openai")
    client = openai.OpenAI(api_key="test-key")

    captured = {}
    client.chat.completions.create = lambda **kw: captured.update(kw) or "OK"  # spy as the "real" create

    from leancontext import wrap_openai
    wrap_openai(client)

    client.chat.completions.create(model="gpt-4o", messages=[_openai_tool_msg()])
    sent = captured["messages"][0]["content"]
    assert len(sent) < len(_big_log()) and "root cause" in sent


def test_wrap_openai_responses_api():
    openai = pytest.importorskip("openai")
    client = openai.OpenAI(api_key="test-key")
    if not hasattr(client, "responses"):
        pytest.skip("Responses API not in this openai version")

    captured = {}
    client.responses.create = lambda **kw: captured.update(kw) or "OK"

    from leancontext import wrap_openai
    wrap_openai(client)

    client.responses.create(
        model="gpt-4o",
        input=[{"type": "function_call_output", "call_id": "c", "output": _big_log()}],
    )
    sent = captured["input"][0]["output"]
    assert len(sent) < len(_big_log()) and "root cause" in sent


def test_wrap_async_openai_client_reduces_messages():
    openai = pytest.importorskip("openai")
    client = openai.AsyncOpenAI(api_key="test-key")

    captured = {}

    async def fake(**kw):
        captured.update(kw)
        return "OK"

    client.chat.completions.create = fake

    from leancontext import wrap_openai
    wrap_openai(client)

    asyncio.run(client.chat.completions.create(model="gpt-4o", messages=[_openai_tool_msg()]))
    sent = captured["messages"][0]["content"]
    assert len(sent) < len(_big_log()) and "root cause" in sent


def test_wrap_anthropic_client_reduces_tool_results():
    anthropic = pytest.importorskip("anthropic")
    client = anthropic.Anthropic(api_key="test-key")

    captured = {}
    client.messages.create = lambda **kw: captured.update(kw) or "OK"

    from leancontext import wrap_anthropic
    wrap_anthropic(client)

    client.messages.create(model="claude-sonnet-4-6", messages=[_anthropic_msg()])
    sent = captured["messages"][0]["content"][0]["content"]
    assert len(sent) < len(_big_log()) and "root cause" in sent


def test_wrap_autodetects_client():
    openai = pytest.importorskip("openai")
    client = openai.OpenAI(api_key="test-key")
    captured = {}
    client.chat.completions.create = lambda **kw: captured.update(kw) or "OK"

    import leancontext
    leancontext.wrap(client)  # generic wrap() should detect an OpenAI client
    client.chat.completions.create(model="gpt-4o", messages=[_openai_tool_msg()])
    assert len(captured["messages"][0]["content"]) < len(_big_log())


# --- standalone proxy --------------------------------------------------------

def test_proxy_reduces_before_forwarding():
    pytest.importorskip("fastapi")
    from starlette.testclient import TestClient

    from leancontext.integrations.proxy import create_app

    captured = {}

    def fake_forward(payload, headers):
        captured.update(payload)
        return {"id": "x", "ok": True}

    app = create_app(forwarder=fake_forward)
    client = TestClient(app)

    resp = client.post("/v1/chat/completions",
                       json={"model": "gpt-4o", "messages": [_openai_tool_msg()]})
    assert resp.status_code == 200
    sent = captured["messages"][0]["content"]
    assert len(sent) < len(_big_log()) and "root cause" in sent


# --- gateway helper: chat (messages) vs Responses (input) --------------------

def test_reduce_messages_in_handles_responses_input_key():
    # Gateway paths use key=None so a Responses request (input=) reduces too, not
    # just chat (messages=). No third-party dependency needed for this logic.
    from leancontext.integrations._common import reduce_messages_in

    data = {"model": "gpt-4o",
            "input": [{"type": "function_call_output", "call_id": "c", "output": _big_log()}]}
    reduce_messages_in(data, "auto", {}, key=None)
    sent = data["input"][0]["output"]
    assert len(sent) < len(_big_log()) and "root cause" in sent


# --- LiteLLM (real CustomLogger) ---------------------------------------------

def test_litellm_pre_call_hook_reduces():
    pytest.importorskip("litellm")
    import leancontext.integrations.litellm as ll

    handler = ll.make_handler()
    data = {"model": "gpt-4o", "messages": [_openai_tool_msg()]}
    out = asyncio.run(handler.async_pre_call_hook(None, None, data, "completion"))
    sent = out["messages"][0]["content"]
    assert len(sent) < len(_big_log()) and "root cause" in sent


def test_litellm_sdk_patch_reduces():
    litellm = pytest.importorskip("litellm")
    import leancontext.integrations.litellm as ll

    spy = {}
    orig = litellm.completion
    litellm.completion = lambda *a, **k: spy.update(k) or "ok"
    litellm._leancontext_patched = False
    ll.patch()
    try:
        litellm.completion(model="x", messages=[_openai_tool_msg()])
        assert len(spy["messages"][0]["content"]) < len(_big_log())
    finally:
        ll.unpatch()
        litellm.completion = orig
        litellm._leancontext_patched = False
