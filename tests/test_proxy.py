import pytest


def _log(n=300):
    lines = [f"2026-06-21T09:00:{i % 60:02d}Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(150, "2026-06-21T09:05:00Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


def _client(forwarder):
    pytest.importorskip("fastapi")
    from starlette.testclient import TestClient

    from leancontext.integrations.proxy import create_app
    return TestClient(create_app(forwarder=forwarder))


def test_proxy_forwards_caller_auth_and_reduces():
    seen = {}

    def fake(payload, headers):
        seen.update(headers)
        seen["messages"] = payload["messages"]
        return {"ok": True}

    resp = _client(fake).post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "tool", "content": _log()}]},
        headers={"Authorization": "Bearer sk-test"},
    )
    assert resp.status_code == 200
    assert seen["authorization"] == "Bearer sk-test"          # caller auth passed through
    assert len(seen["messages"][0]["content"]) < len(_log())  # output reduced first


def test_proxy_returns_502_on_upstream_error():
    def boom(payload, headers):
        raise RuntimeError("upstream down")

    resp = _client(boom).post("/v1/chat/completions", json={"model": "x", "messages": []})
    assert resp.status_code == 502
    assert resp.json()["error"]["type"] == "upstream_error"


def test_proxy_passes_streaming_through():
    pytest.importorskip("fastapi")
    from fastapi.responses import StreamingResponse

    def streamer(payload, headers):
        def gen():
            yield b"data: a\n\n"
            yield b"data: b\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    resp = _client(streamer).post(
        "/v1/chat/completions", json={"model": "x", "messages": [], "stream": True}
    )
    assert resp.status_code == 200
    assert "data: a" in resp.text and "data: b" in resp.text
