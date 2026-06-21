"""Log reducer — the hero.

Strategy: collapse near-identical lines into one representative + a count, while
keeping every anomaly/error line and every *unique* pattern verbatim.

How "near-identical" is decided: we mask the volatile parts of each line
(timestamps, ips, uuids, hex, numbers, quoted strings) to form a *template*.
Lines sharing a template are the same event repeated with different values, so we
keep one and count the rest. Templates that occur once, or that carry a severity
keyword, are always kept verbatim — the rare line is the signal.

Deterministic: dict preserves first-seen order; identical input → identical output.
"""

from __future__ import annotations

import re

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
