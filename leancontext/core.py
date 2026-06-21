"""Dispatch, type detection, the Reduction result, and the fail-open guard.

LeanContext never breaks the caller. If the content type is unknown, a reducer
raises, or the saving or fidelity falls below the configured threshold, we return
the original text unchanged.
"""

from __future__ import annotations

import json
import os
import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

from .fidelity import fidelity_score
from .reducers import reduce_diff, reduce_html, reduce_json, reduce_logs, reduce_stacktrace
from .tokens import content_ref, count_tokens

# --- configuration -----------------------------------------------------------


@dataclass
class _Config:
    min_saving: float = 0.10      # require at least this fractional saving to apply
    min_fidelity: float = 0.85    # require at least this signal preservation to apply
    min_tokens: int = 50          # below this, not worth touching
    max_input_chars: int = 0      # if >0, payloads larger than this pass through untouched
    disabled: bool = False
    cache_size: int = 2048        # max cached reductions; 0 disables the cache
    hooks: list = field(default_factory=list)


CONFIG = _Config()

# A tool output is re-sent on every turn, so we reduce each unique payload once and
# reuse the result. Keyed by content hash + options; deterministic, so this is safe.
_CACHE: OrderedDict[tuple, Reduction] = OrderedDict()


def clear_cache() -> None:
    """Drop all cached reductions."""
    _CACHE.clear()


def disable() -> None:
    CONFIG.disabled = True


def enable() -> None:
    CONFIG.disabled = False


def is_disabled() -> bool:
    return CONFIG.disabled or os.environ.get("LEANCONTEXT_DISABLED", "") == "1"


def on_reduction(callback: Callable[[Reduction], None]) -> Callable[[Reduction], None]:
    """Register a telemetry hook called after each *applied* reduction.

    Composable: multiple hooks may be registered. Returns the callback so it can
    later be passed to :func:`remove_reduction_hook`.
    """
    CONFIG.hooks.append(callback)
    return callback


def remove_reduction_hook(callback: Callable[[Reduction], None]) -> None:
    try:
        CONFIG.hooks.remove(callback)
    except ValueError:
        pass


def clear_reduction_hooks() -> None:
    CONFIG.hooks.clear()


def _emit(reduction: Reduction) -> None:
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
    def tokens_saved(self) -> int:
        return max(0, self.tokens_before - self.tokens_after)

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
    min_saving: float | None = None,
    min_fidelity: float | None = None,
) -> Reduction:
    """Reduce a single piece of content. Always safe: worst case is a no-op.

    Deterministic results are cached by content hash, so a tool output that is
    re-sent across turns is computed only once. Telemetry still fires on every
    call (cache hit or miss), so per-turn savings are recorded as before.
    """
    min_saving = CONFIG.min_saving if min_saving is None else min_saving
    min_fidelity = CONFIG.min_fidelity if min_fidelity is None else min_fidelity

    original = _to_text(content)
    before = count_tokens(original)
    ref = content_ref(original)

    if is_disabled():  # global toggle; never cached so re-enabling takes effect at once
        return _passthrough(original, before, ref, ["disabled"])

    key = (ref, kind, min_saving, min_fidelity, CONFIG.min_tokens, CONFIG.max_input_chars)
    use_cache = CONFIG.cache_size > 0

    if use_cache and key in _CACHE:
        result = _CACHE[key]
        _CACHE.move_to_end(key)
    else:
        result = _compute(original, before, ref, kind, min_saving, min_fidelity)
        if use_cache:
            _CACHE[key] = result
            if len(_CACHE) > CONFIG.cache_size:
                _CACHE.popitem(last=False)  # evict least-recently-used

    if result.applied:
        _emit(result)
    return result


def _compute(original: str, before: int, ref: str, kind: str,
             min_saving: float, min_fidelity: float) -> Reduction:
    """Run detection + the typed reducer. Fail-open: any problem returns the original."""
    def passthrough(notes: list[str]) -> Reduction:
        return _passthrough(original, before, ref, notes)

    if CONFIG.max_input_chars and len(original) > CONFIG.max_input_chars:
        return passthrough(["above max_input_chars"])
    if before < CONFIG.min_tokens:
        return passthrough(["below min_tokens"])

    detected = detect_kind(original) if kind == "auto" else kind
    reducer = REDUCERS.get(detected)
    if reducer is None:
        return passthrough([f"no reducer for kind={detected!r}"])

    try:
        text, notes = reducer(original)
    except Exception as exc:  # fail open on any reducer bug
        return passthrough([f"reducer error: {exc!r}"])

    after = count_tokens(text)
    saving = 0.0 if before == 0 else 1.0 - after / before
    fid = fidelity_score(original, text)

    if saving < min_saving or fid < min_fidelity:
        notes.append(f"reverted: saving={saving:.0%}, fidelity={fid:.0%} (below threshold)")
        return passthrough(notes)

    return Reduction(text, detected, before, after, fid, ref, original, notes)
