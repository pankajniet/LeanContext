from leancontext.core import CONFIG, clear_cache, reduce_text


def _log(n=400):
    lines = [f"2026-06-21T09:00:{i % 60:02d}.000Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(200, "2026-06-21T09:05:00.000Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


def test_no_input_limit_by_default():
    clear_cache()
    assert CONFIG.max_input_chars == 0
    assert reduce_text(_log()).kind == "log"


def test_oversized_input_passes_through():
    clear_cache()
    payload = _log()
    old = CONFIG.max_input_chars
    CONFIG.max_input_chars = 10          # anything bigger is left untouched
    try:
        r = reduce_text(payload)
        assert r.kind == "passthrough"
        assert r.text == payload
    finally:
        CONFIG.max_input_chars = old
        clear_cache()
