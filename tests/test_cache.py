import leancontext
from leancontext.core import CONFIG, clear_cache, reduce_text


def _log(n=400):
    lines = [f"2026-06-21T09:00:{i % 60:02d}.000Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(200, "2026-06-21T09:05:00.000Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


def test_same_input_returns_cached_object():
    clear_cache()
    a = reduce_text(_log())
    b = reduce_text(_log())
    assert a is b                       # cache hit returns the exact same Reduction


def test_clear_cache_recomputes():
    clear_cache()
    a = reduce_text(_log())
    clear_cache()
    b = reduce_text(_log())
    assert a is not b and a.text == b.text   # recomputed, identical result (deterministic)


def test_telemetry_fires_on_every_call_hit_or_miss():
    clear_cache()
    leancontext.clear_reduction_hooks()
    seen = []
    leancontext.on_reduction(lambda r: seen.append(r.kind))
    try:
        reduce_text(_log())   # miss -> compute -> emit
        reduce_text(_log())   # hit  -> emit
        assert seen == ["log", "log"]
    finally:
        leancontext.clear_reduction_hooks()


def test_cache_can_be_disabled():
    clear_cache()
    old = CONFIG.cache_size
    CONFIG.cache_size = 0
    try:
        a = reduce_text(_log())
        b = reduce_text(_log())
        assert a is not b               # no caching when disabled
    finally:
        CONFIG.cache_size = old
        clear_cache()


def test_eviction_bounds_cache_size():
    clear_cache()
    old = CONFIG.cache_size
    CONFIG.cache_size = 2
    try:
        for i in range(5):
            reduce_text(_log() + f"\nunique marker {i} " * 4)   # distinct content each time
        from leancontext.core import _CACHE
        assert len(_CACHE) <= 2         # LRU keeps the cache bounded
    finally:
        CONFIG.cache_size = old
        clear_cache()
