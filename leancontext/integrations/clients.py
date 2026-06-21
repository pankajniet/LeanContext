"""Real SDK client wrappers — OpenAI & Anthropic.

Wraps ``client.chat.completions.create`` (OpenAI) / ``client.messages.create``
(Anthropic) so tool outputs in the outbound ``messages`` are reduced on the wire.
Contract-preserving and fail-open: if anything is unexpected, the original call
runs untouched. Reductions are deterministic, so the prompt-cache prefix stays stable.
"""

from __future__ import annotations

import functools
from typing import Any

from ..messages import reduce_messages


def _wrap_create(create: Any, fmt: str, opts: dict) -> Any:
    @functools.wraps(create)
    def wrapper(*args, **kwargs):
        if "messages" in kwargs:
            try:
                kwargs["messages"] = reduce_messages(kwargs["messages"], fmt=fmt, **opts)
            except Exception:
                pass  # fail open
        return create(*args, **kwargs)

    wrapper.__leancontext_wrapped__ = True  # type: ignore[attr-defined]
    return wrapper


def _already(fn: Any) -> bool:
    return getattr(fn, "__leancontext_wrapped__", False)


def wrap_openai(client: Any, **opts) -> Any:
    """Reduce tool outputs on an OpenAI client's chat.completions.create."""
    try:
        comp = client.chat.completions
        if not _already(comp.create):
            comp.create = _wrap_create(comp.create, "openai", opts)
    except Exception:
        pass  # fail open
    return client


def wrap_anthropic(client: Any, **opts) -> Any:
    """Reduce tool_result blocks on an Anthropic client's messages.create."""
    try:
        msgs = client.messages
        if not _already(msgs.create):
            msgs.create = _wrap_create(msgs.create, "anthropic", opts)
    except Exception:
        pass  # fail open
    return client


def looks_like_openai(obj: Any) -> bool:
    return hasattr(obj, "chat") and hasattr(getattr(obj, "chat"), "completions")


def looks_like_anthropic(obj: Any) -> bool:
    return hasattr(obj, "messages") and hasattr(getattr(obj, "messages"), "create") \
        and not looks_like_openai(obj)
