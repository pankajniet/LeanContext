"""Token counting.

By default LeanContext uses the best tokenizer available: if ``tiktoken`` is
installed it is used automatically for accurate counts, otherwise a fast
character-based estimate (about 4 characters per token) is used. You can also
plug in your own counter with ``set_token_counter`` or ``use_tiktoken(model)``.

Token counts only affect the reported numbers and the saving threshold, never the
reduced text, so the reduction is the same whichever tokenizer is active.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

_counter: Callable[[str], int] | None = None   # explicit override, if set
_auto: Callable[[str], int] | None = None       # resolved once, on first use
_auto_name = "unresolved"


def content_ref(text: str) -> str:
    """Short, stable content hash used as a handle for caching and paging."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _heuristic(text: str) -> int:
    return max(1, (len(text) + 3) // 4)   # about 4 characters per token


def _resolve_auto() -> None:
    """Pick the default tokenizer once: tiktoken if present, else the estimate."""
    global _auto, _auto_name
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")

        def _tok(text: str) -> int:
            return len(enc.encode(text, disallowed_special=()))

        _auto, _auto_name = _tok, "tiktoken/cl100k_base"
    except Exception:
        _auto, _auto_name = _heuristic, "heuristic (~4 chars/token)"


def count_tokens(text: str) -> int:
    """Count the tokens in ``text`` using the active tokenizer."""
    if _counter is not None:
        return _counter(text)
    if _auto is None:
        _resolve_auto()
    return _auto(text)  # type: ignore[misc]


def _invalidate_cache() -> None:
    # token counts feed cached reductions' numbers and the revert decision, so a
    # tokenizer change must drop the cache to avoid returning stale counts.
    try:
        from .core import clear_cache

        clear_cache()
    except Exception:
        pass


def set_token_counter(fn: Callable[[str], int] | None) -> None:
    """Set a custom token counter, or pass None to fall back to auto-detection."""
    global _counter
    _counter = fn
    _invalidate_cache()


def use_tiktoken(model: str = "gpt-4o") -> None:
    """Count tokens with tiktoken for a specific model. Requires the tiktoken extra."""
    import tiktoken

    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    set_token_counter(lambda text: len(enc.encode(text, disallowed_special=())))


def active_tokenizer() -> str:
    """Name of the tokenizer currently in use."""
    if _counter is not None:
        return "custom"
    if _auto is None:
        _resolve_auto()
    return _auto_name
