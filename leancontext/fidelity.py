"""Fidelity scoring: did the signal survive the reduction?

The score is per content type. For logs and text we check that error/anomaly
lines and the values on them are kept. Each structured type checks the invariant
that makes its reduction safe: JSON matches every scalar value as a whole encoded
token (multiset); diff keeps every change line; a stack trace keeps every
exception message and chain marker; HTML keeps the distinct visible words; a table
keeps each row's non-space content. Matching is by whole token, not substring, so
a dropped value can't be masked by a longer one that contains it. If the score
falls below the threshold, the core reverts to the original.
"""

from __future__ import annotations

import json
import re
from collections import Counter
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


# JSON scalar tokens, matched as whole tokens (not substrings): a quoted string is
# self-delimiting, and a number is bounded so "1" no longer counts as preserved just
# because it sits inside "100" or "0.1".
_JSON_STR = re.compile(r'"(?:[^"\\]|\\.)*"')
_JSON_NUM = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")


def _scalar_tokens(text: str) -> Counter:
    """Multiset of JSON scalar tokens (quoted strings, then numbers) found in ``text``."""
    counts: Counter = Counter()
    for m in _JSON_STR.finditer(text):
        counts[m.group()] += 1
    # Strip strings first so digits inside a string value aren't counted as numbers.
    for m in _JSON_NUM.finditer(_JSON_STR.sub(" ", text)):
        counts[m.group()] += 1
    return counts


def _json_fidelity(original: str, reduced: str) -> float:
    """Fraction of JSON scalar values (strings and numbers) preserved in the output.

    Values are matched in their JSON-encoded form (the reducer emits them that way)
    as a *multiset*: a value counts as preserved only if a distinct, whole encoded
    token survives for it. So dropping a record whose value happens to be a substring
    of a surviving one (e.g. "1" inside "100"), or dropping one of several duplicates,
    lowers the score — the check sees structural loss, not mere character overlap.
    """
    try:
        data = json.loads(original)
    except Exception:
        return 1.0
    want: Counter = Counter()
    for v in _iter_scalars(data):
        want[json.dumps(v, ensure_ascii=False)] += 1
    if not want:
        return 1.0
    have = _scalar_tokens(reduced)
    kept = sum(min(n, have.get(tok, 0)) for tok, n in want.items())
    return kept / sum(want.values())


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
    """Every exception/chain line must be preserved, not only the last.

    The non-indented lines of a traceback carry its semantics: each exception
    message and each chain marker ("During handling of the above exception ...",
    "The above exception was the direct cause ..."). Frame lines (``File "..."``,
    source, carets) are indented and may be collapsed. We exclude the structural
    ``Traceback (most recent call last):`` header (a reduction may abbreviate it),
    and require every remaining non-indented line to survive — so a *chained*
    traceback whose earlier root cause is collapsed scores low and reverts, instead
    of silently dropping the cause as the old last-line-only check allowed.
    """
    semantic = [
        ln for ln in original.splitlines()
        if ln.strip() and ln[:1] not in (" ", "\t")
        and ln.strip() != "Traceback (most recent call last):"
    ]
    if not semantic:
        return 1.0
    kept = sum(1 for ln in semantic if ln in reduced)
    return kept / len(semantic)


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
    # Distinct words, matched as whole tokens against the output's word set. Counting
    # distinct words (not every occurrence) stops a flood of common words like "the"
    # from masking the loss of a few rare-but-important ones; whole-token matching
    # stops "cat" from counting as present because the output contains "category".
    words = {w for part in parser.parts for w in part.split() if w}
    if not words:
        return 1.0
    have = set(reduced.split())
    kept = sum(1 for w in words if w in have)
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
