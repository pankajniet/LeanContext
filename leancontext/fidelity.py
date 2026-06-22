"""Fidelity scoring: did the signal survive the reduction?

The score is per content type. For logs and text we check that error/anomaly
lines and the values on them are kept. For JSON, diff, and stack traces we check
the type-specific invariants that make those reductions safe (all values, all
change lines, the exception). If the score falls below the threshold, the core
reverts to the original.
"""

from __future__ import annotations

import json
import re
from typing import Any

_SEVERITY = re.compile(r"(?i)\b(error|fatal|critical|exception|panic|traceback|warn|warning)\b")
_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_HEX = re.compile(r"0x[0-9a-fA-F]+")
_PATH = re.compile(r"(?:/[\w.\-]+){2,}")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_QUOTE = re.compile(r'"[^"]*"')

_VALUE_PATTERNS = (_UUID, _HEX, _PATH, _NUM, _QUOTE)


def _norm(line: str) -> str:
    return " ".join(line.split())


def salient_items(text: str) -> set[str]:
    """The must-not-lose items in logs/text: error lines and the values on them."""
    items: set[str] = set()
    for line in text.splitlines():
        if _SEVERITY.search(line):
            items.add(_norm(line))
            for rx in _VALUE_PATTERNS:
                items.update(rx.findall(line))
    return items


def _signal_score(original: str, reduced: str) -> float:
    """Fraction of the original's salient items still present (logs/text/html)."""
    items = salient_items(original)
    if not items:
        return 1.0
    reduced_lines = {_norm(line) for line in reduced.splitlines()}
    kept = sum(1 for item in items if item in reduced_lines or item in reduced)
    return kept / len(items)


def _iter_scalars(data: Any):
    if isinstance(data, dict):
        for value in data.values():
            yield from _iter_scalars(value)
    elif isinstance(data, list):
        for item in data:
            yield from _iter_scalars(item)
    elif isinstance(data, (str, int, float)) and not isinstance(data, bool):
        yield data


def _json_fidelity(original: str, reduced: str) -> float:
    """Fraction of JSON scalar values (strings and numbers) preserved in the output.

    Values are matched in their JSON-encoded form (the reducer emits them that way),
    so a value containing a delimiter, quote, or newline only counts as preserved if
    its exact escaped bytes survive — the check sees structural corruption, not just
    whether the characters appear somewhere.
    """
    try:
        data = json.loads(original)
    except Exception:
        return 1.0
    values = [
        json.dumps(v, ensure_ascii=False).strip('"')
        for v in _iter_scalars(data)
    ]
    values = [v for v in values if v]
    if not values:
        return 1.0
    kept = sum(1 for v in values if v in reduced)
    return kept / len(values)


def _diff_fidelity(original: str, reduced: str) -> float:
    """Fraction of changed (+/-) lines preserved verbatim."""
    changes = [
        ln for ln in original.splitlines()
        if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
    ]
    if not changes:
        return 1.0
    reduced_lines = set(reduced.splitlines())
    kept = sum(1 for ln in changes if ln in reduced_lines)
    return kept / len(changes)


def _stacktrace_fidelity(original: str, reduced: str) -> float:
    """The exception line (the last non-empty line) must be preserved."""
    lines = [ln for ln in original.splitlines() if ln.strip()]
    if not lines:
        return 1.0
    return 1.0 if lines[-1] in reduced else 0.0


def _html_fidelity(original: str, reduced: str) -> float:
    """Fraction of the original's visible-text words preserved in the output.

    Reuses the HTML reducer's own extractor, so the check measures exactly what the
    reduction is supposed to keep (visible text, not tags/scripts). A correct strip
    keeps every word and scores ~1.0; dropping body text drops the score — unlike a
    generic salience check, which is blind to lost prose with no error keywords.
    """
    from .reducers.html import _Extract  # local import avoids an import cycle

    parser = _Extract()
    try:
        parser.feed(original)
    except Exception:
        return 1.0
    words = [w for part in parser.parts for w in part.split() if w]
    if not words:
        return 1.0
    kept = sum(1 for w in words if w in reduced)
    return kept / len(words)


def _table_fidelity(original: str, reduced: str) -> float:
    """Fraction of table rows whose non-space content survives.

    The table reducer only removes whitespace, so every row's non-space characters
    must still appear (in order) in the output. Stripping all whitespace before
    comparing ignores the alignment the reducer is allowed to drop, while still
    catching a dropped row or a lost value character.
    """
    rows = [re.sub(r"\s+", "", ln) for ln in original.splitlines() if ln.strip()]
    rows = [r for r in rows if r]
    if not rows:
        return 1.0
    blob = re.sub(r"\s+", "", reduced)
    kept = sum(1 for r in rows if r in blob)
    return kept / len(rows)


_TYPED = {
    "json": _json_fidelity,
    "diff": _diff_fidelity,
    "stacktrace": _stacktrace_fidelity,
    "html": _html_fidelity,
    "table": _table_fidelity,
}


def fidelity_score(original: str, reduced: str, kind: str = "text") -> float:
    """Score how well the reduction preserved the signal, using a per-type check."""
    scorer = _TYPED.get(kind)
    if scorer is not None:
        return scorer(original, reduced)
    return _signal_score(original, reduced)
