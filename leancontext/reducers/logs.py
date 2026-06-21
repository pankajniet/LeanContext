"""Collapse repetitive log lines.

Near-identical lines collapse to one representative plus a count, while every
error/anomaly line and every one-off pattern is kept as-is.

To decide "near-identical", we mask the volatile parts of a line (timestamps, ips,
uuids, hex, numbers, quoted strings) into a template. Lines that share a template
are the same event with different values, so we keep one and count the rest.
Templates seen only once, or carrying a severity keyword, are kept verbatim, since
the rare line is usually the one that matters.

Deterministic: first-seen order is preserved, so the same input gives the same output.
"""

from __future__ import annotations

import re

from .base import Reducer

_LOG_HINT = re.compile(
    r"(?im)^\s*(?:\d{4}-\d{2}-\d{2}[T ]|\[?(?:INFO|DEBUG|WARN|WARNING|ERROR|FATAL|TRACE|CRITICAL)\b)"
)
_SEVERITY = re.compile(r"(?i)\b(ERROR|FATAL|CRITICAL|EXCEPTION|PANIC|TRACEBACK|WARN|WARNING)\b")

# Order matters: more specific patterns first so they win before the generic
# number mask consumes their digits.
_MASKS = (
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ][\d:.,]+(?:Z|[+-]\d{2}:?\d{2})?"), "§ts"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "§ip"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "§uuid"),
    (re.compile(r"0x[0-9a-fA-F]+"), "§hex"),
    (re.compile(r'"[^"]*"'), "§s"),
    (re.compile(r"\b\d+(?:\.\d+)?\b"), "§n"),
)


def _template(line: str) -> str:
    t = line
    for rx, repl in _MASKS:
        t = rx.sub(repl, t)
    return t.strip()


def reduce_logs(text: str) -> tuple[str, list[str]]:
    lines = text.splitlines()
    groups: dict[str, list] = {}  # template -> [representative, count, is_severity]
    order: list[str] = []

    for line in lines:
        if not line.strip():
            continue
        key = _template(line)
        sev = bool(_SEVERITY.search(line))
        g = groups.get(key)
        if g is None:
            groups[key] = [line, 1, sev]
            order.append(key)
        else:
            g[1] += 1
            g[2] = g[2] or sev

    out: list[str] = []
    kept_verbatim = 0
    for key in order:
        line, count, is_sev = groups[key]
        if is_sev:
            kept_verbatim += 1
            out.append(line if count == 1 else f"{line}    ⟪×{count}⟫")
        elif count == 1:
            kept_verbatim += 1
            out.append(line)
        else:
            out.append(f"{line}    ⟪×{count} similar⟫")

    notes = [
        f"{len(order)} unique patterns from {len(lines)} lines; "
        f"{kept_verbatim} anomaly/unique lines kept verbatim"
    ]
    return "\n".join(out), notes


def _detect(text: str) -> bool:
    lines = text.splitlines()
    if len(lines) < 5:
        return False
    hits = sum(1 for ln in lines if _LOG_HINT.match(ln))
    return hits >= max(3, len(lines) * 0.3)


REDUCER = Reducer("log", _detect, reduce_logs, priority=50)
