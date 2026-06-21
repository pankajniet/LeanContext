"""Shared plumbing for integration wrappers.

One place for the fail-open "wrap a ``create(**kwargs)`` callable, reduce its
``messages``, and mark it so we don't double-wrap" pattern, reused by the OpenAI/
Anthropic client wrappers, the Anthropic-native wrapper, and LiteLLM.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from ..messages import reduce_messages

_MARKER = "__leancontext_wrapped__"


def is_wrapped(fn: Any) -> bool:
    return getattr(fn, _MARKER, False)


def mark(fn: Callable) -> Callable:
    setattr(fn, _MARKER, True)
    return fn


#: Request keys that can carry a message/tool-output list across providers:
#: ``messages`` (OpenAI chat / Anthropic), ``input`` (OpenAI Responses API).
_LIST_KEYS = ("messages", "input")


def reduce_messages_in(mapping: Any, fmt: str, opts: dict, key: str | None = "messages") -> None:
    """Fail-open, in-place reduction of the message list(s) in ``mapping`` (dict-like).

    ``key`` names the field to reduce (``messages`` for OpenAI/Anthropic). Pass
    ``key=None`` to reduce whichever known list keys are present — used on gateway
    paths (LiteLLM) where a request may be chat (``messages``) or Responses (``input``).
    """
    if not isinstance(mapping, dict):
        return
    keys = _LIST_KEYS if key is None else (key,)
    for k in keys:
        if isinstance(mapping.get(k), list):
            try:
                mapping[k] = reduce_messages(mapping[k], fmt=fmt, **opts)
            except Exception:
                pass  # fail open


def wrap_messages_create(create: Callable, *, fmt: str, opts: dict, key: str | None = "messages",
                         reduce: bool = True,
                         before: Callable[[dict], None] | None = None) -> Callable:
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
