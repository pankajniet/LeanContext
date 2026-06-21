"""Core: dispatch, type detection, the Reduction result, and the fail-open guard.

The cardinal rule (see AGENTS.md §5C): LeanContext can only ever *help or no-op*. If the
type is unknown, a reducer raises, the saving is too small, or fidelity is too low,
we return the ORIGINAL text unchanged. Nothing here can corrupt an agent workflow.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from .fidelity import fidelity_score
from .reducers import reduce_diff, reduce_html, reduce_json, reduce_logs, reduce_stacktrace
from .tokens import count_tokens

# --- configuration -----------------------------------------------------------


@dataclass
class _Config:
    min_saving: float = 0.10      # require at least this fractional saving to apply
    min_fidelity: float = 0.85    # require at least this signal preservation to apply
    min_tokens: int = 50          # below this, not worth touching
    disabled: bool = False
    hooks: list = field(default_factory=list)


CONFIG = _Config()


def disable() -> None:
    CONFIG.disabled = True


def enable() -> None:
    CONFIG.disabled = False


def is_disabled() -> bool:
    return CONFIG.disabled or os.environ.get("LEANCONTEXT_DISABLED", "") == "1"


def on_reduction(callback: Callable[["Reduction"], None]) -> Callable[["Reduction"], None]:
    """Register a telemetry hook called after each *applied* reduction.

    Composable: multiple hooks may be registered. Returns the callback so it can
    later be passed to :func:`remove_reduction_hook`.
    """
    CONFIG.hooks.append(callback)
    return callback


def remove_reduction_hook(callback: Callable[["Reduction"], None]) -> None:
    try:
        CONFIG.hooks.remove(callback)
    except ValueError:
        pass


def clear_reduction_hooks() -> None:
    CONFIG.hooks.clear()


def _emit(reduction: "Reduction") -> None:
    for callback in list(CONFIG.hooks):
        try:
            callback(reduction)
        except Exception:
            pass  # telemetry must never break the agent


# --- result ------------------------------------------------------------------


@dataclass
class Reduction:
    text: str            # the string to send to the model
    kind: str            # detected/used content kind ("log", "json", "passthrough", ...)
    tokens_before: int
    tokens_after: int
    fidelity: float      # 0..1 signal preserved
    ref: str             # content hash of the ORIGINAL (handle for paging/restore)
    original: str
    notes: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        if self.tokens_before == 0:
            return 0.0
        return 1.0 - self.tokens_after / self.tokens_before

    @property
    def applied(self) -> bool:
        return self.kind != "passthrough"

    def __str__(self) -> str:  # so `str(reduction)` / f-strings give the payload
        return self.text


# --- detection & dispatch ----------------------------------------------------

REDUCERS: dict[str, Callable[[str], tuple[str, list[str]]]] = {
    "log": reduce_logs,
    "json": reduce_json,
    "diff": reduce_diff,
    "stacktrace": reduce_stacktrace,
    "html": reduce_html,
}

_LOG_HINT = re.compile(
    r"(?im)^\s*(?:\d{4}-\d{2}-\d{2}[T ]|\[?(?:INFO|DEBUG|WARN|WARNING|ERROR|FATAL|TRACE|CRITICAL)\b)"
)
_DIFF_HUNK = re.compile(r"(?m)^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")


def _looks_like_diff(text: str) -> bool:
    return text.lstrip().startswith("diff --git") or bool(_DIFF_HUNK.search(text))


def _looks_like_html(text: str) -> bool:
    stripped = text.lstrip()
    head = stripped[:512].lower()
    if "<!doctype html" in head or "<html" in head:
        return True
    return stripped.startswith("<") and text.lower().count("</") >= 5


def detect_kind(text: str) -> str:
    stripped = text.lstrip()
    if stripped[:1] in "[{":
        try:
            json.loads(text)
            return "json"
        except Exception:
            pass
    if "Traceback (most recent call last)" in text:
        return "stacktrace"
    if _looks_like_diff(text):
        return "diff"
    if _looks_like_html(text):
        return "html"
    lines = text.splitlines()
    if len(lines) >= 5:
        hits = sum(1 for ln in lines if _LOG_HINT.match(ln))
        if hits >= max(3, len(lines) * 0.3):
            return "log"
    return "text"


def _to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _passthrough(original: str, before: int, ref: str, notes: list[str]) -> Reduction:
    return Reduction(original, "passthrough", before, before, 1.0, ref, original, notes)


def reduce_text(
    content: object,
    *,
    kind: str = "auto",
    min_saving: Optional[float] = None,
    min_fidelity: Optional[float] = None,
) -> Reduction:
    """Reduce a single piece of content. Always safe: worst case is a no-op."""
    min_saving = CONFIG.min_saving if min_saving is None else min_saving
    min_fidelity = CONFIG.min_fidelity if min_fidelity is None else min_fidelity

    original = _to_text(content)
    before = count_tokens(original)
    ref = hashlib.sha1(original.encode("utf-8")).hexdigest()[:12]

    if is_disabled():
        return _passthrough(original, before, ref, ["disabled"])
    if before < CONFIG.min_tokens:
        return _passthrough(original, before, ref, ["below min_tokens"])

    detected = detect_kind(original) if kind == "auto" else kind
    reducer = REDUCERS.get(detected)
    if reducer is None:
        return _passthrough(original, before, ref, [f"no reducer for kind={detected!r}"])

    try:
        text, notes = reducer(original)
    except Exception as exc:  # fail open on any reducer bug
        return _passthrough(original, before, ref, [f"reducer error: {exc!r}"])

    after = count_tokens(text)
    saving = 0.0 if before == 0 else 1.0 - after / before
    fid = fidelity_score(original, text)

    if saving < min_saving or fid < min_fidelity:
        notes.append(f"reverted: saving={saving:.0%}, fidelity={fid:.0%} (below threshold)")
        return _passthrough(original, before, ref, notes)

    result = Reduction(text, detected, before, after, fid, ref, original, notes)
    _emit(result)
    return result
