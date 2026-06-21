"""Pluggable token counting.

Default is a fast, dependency-free heuristic (~4 chars/token). Swap in a real
tokenizer with ``set_token_counter`` or ``use_tiktoken`` when you want exact
billing numbers. The reduction path never depends on a real tokenizer being
present — accounting precision is orthogonal to safety.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

_counter: Callable[[str], int] | None = None


def content_ref(text: str) -> str:
    """Short, stable content hash — the handle used for caching and paging."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def count_tokens(text: str) -> int:
    """Estimate the token count of ``text``."""
    if _counter is not None:
        return _counter(text)
    # Heuristic: ~4 characters per token. Good enough for ratios and triage;
    # use a real tokenizer for exact cost figures.
    return max(1, (len(text) + 3) // 4)


def set_token_counter(fn: Callable[[str], int]) -> None:
    """Install a custom token counter (e.g. an Anthropic/OpenAI tokenizer)."""
    global _counter
    _counter = fn


def use_tiktoken(model: str = "gpt-4o") -> None:
    """Use tiktoken for exact counts. Requires the ``tiktoken`` extra."""
    import tiktoken  # optional dependency

    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    set_token_counter(lambda t: len(enc.encode(t)))
