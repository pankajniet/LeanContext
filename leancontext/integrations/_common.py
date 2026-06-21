"""Shared plumbing for integration wrappers.

One place for the fail-open "wrap a ``create(**kwargs)`` callable, reduce its
``messages``, and mark it so we don't double-wrap" pattern, reused by the OpenAI/
Anthropic client wrappers, the Anthropic-native wrapper, and LiteLLM.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional

from ..messages import reduce_messages

_MARKER = "__leancontext_wrapped__"


def is_wrapped(fn: Any) -> bool:
    return getattr(fn, _MARKER, False)


def mark(fn: Callable) -> Callable:
    setattr(fn, _MARKER, True)
    return fn


def reduce_messages_in(mapping: Any, fmt: str, opts: dict, key: str = "messages") -> None:
    """Fail-open, in-place reduction of ``mapping[key]`` (dict-like).

    ``key`` is ``messages`` for OpenAI/Anthropic, ``contents`` for Gemini.
    """
    if isinstance(mapping, dict) and isinstance(mapping.get(key), list):
        try:
            mapping[key] = reduce_messages(mapping[key], fmt=fmt, **opts)
        except Exception:
            pass  # fail open


def wrap_messages_create(create: Callable, *, fmt: str, opts: dict, key: str = "messages",
                         reduce: bool = True,
                         before: Optional[Callable[[dict], None]] = None) -> Callable:
    """Wrap a ``create(**kwargs)`` callable to reduce its messages before calling through.

    ``before`` runs after reduction (e.g. to inject provider params/headers).
    Idempotent: an already-wrapped callable is returned unchanged.
    """
    if is_wrapped(create):
        return create

    @functools.wraps(create)
    def wrapper(*args, **kwargs):
        if reduce:
            reduce_messages_in(kwargs, fmt, opts, key=key)
        if before is not None:
            try:
                before(kwargs)
            except Exception:
                pass  # fail open
        return create(*args, **kwargs)

    return mark(wrapper)
