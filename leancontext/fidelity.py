"""Fidelity scoring: did the signal survive the reduction?

"Signal" here means the things an agent shouldn't lose: error/anomaly lines and
the values on them (ids, hex addresses, file paths, numbers, quoted strings).
Routine high-frequency noise (most INFO logs) isn't counted as signal, since
collapsing it is what we want.

If a reducer drops an error line or mangles an id on one, the score falls and the
core reverts to the original.
"""

from __future__ import annotations

import re

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
    """Extract the must-not-lose items: error lines and the values on them."""
    items: set[str] = set()
    for line in text.splitlines():
        if _SEVERITY.search(line):
            items.add(_norm(line))
            for rx in _VALUE_PATTERNS:
                items.update(rx.findall(line))
    return items


def fidelity_score(original: str, reduced: str) -> float:
    """Fraction of the original's salient items still present in ``reduced``.

    Returns 1.0 when there is nothing critical to preserve.
    """
    items = salient_items(original)
    if not items:
        return 1.0
    reduced_lines = {_norm(line) for line in reduced.splitlines()}
    kept = 0
    for item in items:
        if item in reduced_lines or item in reduced:
            kept += 1
    return kept / len(items)
