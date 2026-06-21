"""Real SDK client wrappers — OpenAI & Anthropic.

Wraps ``client.chat.completions.create`` (OpenAI) / ``client.messages.create``
(Anthropic) so tool outputs in the outbound ``messages`` are reduced on the wire.
Contract-preserving and fail-open: if anything is unexpected, the original call
runs untouched. Reductions are deterministic, so the prompt-cache prefix stays stable.
"""

from __future__ import annotations

from typing import Any

from ._common import wrap_messages_create


def wrap_openai(client: Any, **opts) -> Any:
    """Reduce tool outputs on an OpenAI client's chat.completions.create."""
    try:
        comp = client.chat.completions
        comp.create = wrap_messages_create(comp.create, fmt="openai", opts=opts)
    except Exception:
        pass  # fail open
    return client


def wrap_anthropic(client: Any, **opts) -> Any:
    """Reduce tool_result blocks on an Anthropic client's messages.create."""
    try:
        client.messages.create = wrap_messages_create(client.messages.create, fmt="anthropic", opts=opts)
    except Exception:
        pass  # fail open
    return client


def looks_like_openai(obj: Any) -> bool:
    return hasattr(obj, "chat") and hasattr(getattr(obj, "chat"), "completions")


def looks_like_anthropic(obj: Any) -> bool:
    return hasattr(obj, "messages") and hasattr(getattr(obj, "messages"), "create") \
        and not looks_like_openai(obj)
