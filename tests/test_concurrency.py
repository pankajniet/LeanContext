import concurrent.futures

import leancontext
from leancontext.core import CONFIG, clear_cache


def _log(n=400):
    lines = [f"2026-06-21T09:00:{i % 60:02d}Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(200, "2026-06-21T09:05:00Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


def test_concurrent_reduce_with_eviction_is_safe():
    # Small cache + many distinct payloads across threads exercises the cache's
    # insert / move_to_end / evict paths concurrently. With the lock this is safe.
    clear_cache()
    old = CONFIG.cache_size
    CONFIG.cache_size = 5
    try:
        payloads = [_log() + f"\nunique-{i} marker line " * 2 for i in range(60)] * 2
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda p: leancontext.reduce(p).text, payloads))
        assert len(results) == len(payloads)
        assert all("root cause" in r for r in results)
    finally:
        CONFIG.cache_size = old
        clear_cache()
