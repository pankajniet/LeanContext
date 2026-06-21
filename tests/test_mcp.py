import pytest

from leancontext import paging
from leancontext.integrations import mcp_server


def _log(n=400):
    lines = [f"2026-06-21T09:00:{i % 60:02d}Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(200, "2026-06-21T09:05:00Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


def test_reduce_tool_shrinks_and_keeps_signal():
    out = mcp_server.reduce(_log())
    assert "root cause" in out and len(out) < len(_log())


def test_expand_tool_roundtrip_and_missing():
    ref = paging.store("important original content " * 20)
    assert mcp_server.expand(ref).startswith("important original content")
    assert "No content found" in mcp_server.expand("lc://deadbeef00")


def test_stats_tool_reports_metrics():
    s = mcp_server.stats(_log())
    assert s["kind"] == "log"
    assert s["tokens_after"] < s["tokens_before"]
    assert 0.0 <= s["fidelity"] <= 1.0


def test_create_server_builds():
    pytest.importorskip("mcp")
    server = mcp_server.create_server()
    assert server is not None
