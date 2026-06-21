"""Diff reducer.

Keeps every change line (``+``/``-``), hunk header (``@@``) and file header verbatim
— those are the signal. Collapses long runs of unchanged context lines to the first
and last line plus a count. Deterministic; value-preserving for all changes.
"""

from __future__ import annotations

import re

from .base import Reducer

_DIFF_HUNK = re.compile(r"(?m)^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")

_KEEP_PREFIXES = (
    "+", "-", "@@", "diff ", "index ", "new file", "deleted file",
    "rename ", "similarity ", "copy ", "old mode", "new mode",
)


def reduce_diff(text: str) -> tuple[str, list[str]]:
    lines = text.splitlines()
    out: list[str] = []
    ctx: list[str] = []

    def flush() -> None:
        if not ctx:
            return
        if len(ctx) <= 3:
            out.extend(ctx)
        else:
            out.append(ctx[0])
            out.append(f"  ⟪… {len(ctx) - 2} unchanged lines⟫")
            out.append(ctx[-1])
        ctx.clear()

    for line in lines:
        if line.startswith(_KEEP_PREFIXES):
            flush()
            out.append(line)
        else:
            ctx.append(line)
    flush()

    notes = [f"kept all change/header lines; collapsed unchanged context ({len(lines)}→{len(out)} lines)"]
    return "\n".join(out), notes


def _detect(text: str) -> bool:
    return text.lstrip().startswith("diff --git") or bool(_DIFF_HUNK.search(text))


REDUCER = Reducer("diff", _detect, reduce_diff, priority=30)
