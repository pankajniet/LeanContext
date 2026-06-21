"""Whitespace-aligned table reducer.

Command-line tools (kubectl, docker, ps, ls -l, df) pad columns with runs of
spaces so they line up. That padding is pure tokens. We collapse each run of two
or more spaces to a single space and trim line ends. Every value is kept; only
the alignment is dropped, so this is lossless for the data.
"""

from __future__ import annotations

import re

from .base import Reducer

_GAP = re.compile(r"[ \t]{2,}")


def reduce_table(text: str) -> tuple[str, list[str]]:
    out = [_GAP.sub(" ", line).rstrip() for line in text.splitlines()]
    return "\n".join(out), ["collapsed column padding; values preserved"]


def _detect(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    # A line looks columnar when it has at least two padded gaps (3+ columns).
    columnar = sum(1 for ln in lines if len(_GAP.findall(ln)) >= 2)
    return columnar >= max(3, len(lines) * 0.6)


REDUCER = Reducer("table", _detect, reduce_table, priority=60)
