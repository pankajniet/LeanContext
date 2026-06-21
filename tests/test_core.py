import json

import leancontext
from leancontext.core import reduce_text


def _log(n=600):
    lines = []
    for i in range(n):
        lines.append(f"2026-06-21T09:00:{i % 60:02d}.000Z INFO [worker] job={i} status=ok ms={i % 50}")
    lines.insert(300, "2026-06-21T09:05:00.000Z FATAL [render] OOM killed worker=7 doc=deck-42 — root cause")
    return "\n".join(lines)


def test_log_reduces_and_keeps_fatal():
    r = leancontext.reduce(_log())
    assert r.kind == "log"
    assert r.ratio > 0.5
    assert "root cause" in r.text          # the signal survived
    assert r.fidelity == 1.0


def test_determinism():
    payload = _log()
    a = reduce_text(payload).text
    b = reduce_text(payload).text
    assert a == b                          # cache-stable: identical in -> identical out


def test_fail_open_on_small_input():
    r = leancontext.reduce("just a short string")
    assert r.kind == "passthrough"
    assert r.text == "just a short string"


def test_json_columnar_is_lossless_on_values():
    records = [{"id": i, "name": f"n{i}", "score": i / 10} for i in range(20)]
    r = leancontext.reduce(json.dumps(records))
    assert r.kind == "json"
    assert r.ratio > 0.2
    for i in range(20):
        assert f"n{i}" in r.text           # every value preserved


def test_json_columnar_handles_delimiter_and_newline_values():
    # Values containing the column delimiter or a newline must not corrupt rows:
    # each row must parse back to exactly its original fields (regression test).
    records = [{"id": i, "text": f"row {i} | part A\nrow {i} part B", "n": i} for i in range(10)]
    r = leancontext.reduce(json.dumps(records))
    assert r.kind == "json"                 # reduction applied, not reverted
    rows = [json.loads(line) for line in r.text.splitlines()[1:]]  # skip the fields header
    assert rows == [[i, f"row {i} | part A\nrow {i} part B", i] for i in range(10)]

def test_decorator_preserves_contract():
    @leancontext.reduce
    def tool(_: str) -> str:
        return _log()

    out = tool("q")
    assert isinstance(out, str)            # str in -> str out
    assert "root cause" in out

    @leancontext.reduce
    def non_str_tool() -> dict:
        return {"a": 1}

    assert non_str_tool() == {"a": 1}      # non-str passed through untouched


def test_kill_switch():
    payload = _log()
    leancontext.disable()
    try:
        assert leancontext.reduce(payload).kind == "passthrough"
    finally:
        leancontext.enable()
    assert leancontext.reduce(payload).kind == "log"
