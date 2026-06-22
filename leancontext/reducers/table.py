"""Whitespace-aligned table reducer.

Command-line tools (kubectl, docker, ps, ls -l, df) pad columns with runs of
spaces so they line up. That padding is pure tokens. We detect the column start
positions (the columns that begin a field across the rows), slice each row into
cells at those boundaries, and drop only each cell's *trailing* alignment padding
— a value's own internal spaces are kept. Cells are rejoined with one space.

A whitespace table is ambiguous by nature: a value that overflows its column, or
trailing spaces inside a value, can't be told apart from padding. The fidelity
check (fidelity._table_fidelity) verifies no row or value character is dropped and
reverts to the original if so, so an odd table fails open instead of corrupting.
"""

from __future__ import annotations

import re

from .base import Reducer

_GAP = re.compile(r"[ \t]{2,}")


def _padding_columns(rows: list[str], width: int) -> list[bool]:
    """A column index is padding only if it is blank (space/tab/past end) in every row."""
    pad = [True] * width
    for ln in rows:
        for i in range(min(len(ln), width)):
            if ln[i] not in " \t":
                pad[i] = False
    return pad


def reduce_table(text: str) -> tuple[str, list[str]]:
    lines = text.split("\n")
    rows = [ln for ln in lines if ln.strip()]
    if len(rows) < 2:
        return text, ["no table detected"]
    width = max(len(ln) for ln in rows)
    pad = _padding_columns(rows, width)

    # A column starts where content begins after a padding gap (or at position 0).
    starts = [i for i in range(width) if not pad[i] and (i == 0 or pad[i - 1])]
    if len(starts) < 2:
        return text, ["no columns detected"]

    out: list[str] = []
    for ln in lines:
        if not ln.strip():
            out.append("")
            continue
        cells = []
        for k, s in enumerate(starts):
            end = starts[k + 1] if k + 1 < len(starts) else len(ln)
            cells.append(ln[s:end].rstrip())   # drop trailing pad, keep internal spaces
        out.append(" ".join(cells).rstrip())
    return "\n".join(out), [f"collapsed padding across {len(starts)} columns; cell values preserved"]


def _detect(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    # A line looks columnar when it has at least two padded gaps (3+ columns).
    columnar = sum(1 for ln in lines if len(_GAP.findall(ln)) >= 2)
    return columnar >= max(3, len(lines) * 0.6)


REDUCER = Reducer("table", _detect, reduce_table, priority=60)
