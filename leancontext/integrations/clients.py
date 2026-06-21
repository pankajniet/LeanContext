"""SDK client wrappers for OpenAI, Anthropic, and Gemini.

Wraps the provider's call (OpenAI ``chat.completions.create``, Anthropic
``messages.create``, Gemini ``models.generate_content``) so tool outputs in the
outbound request are reduced before they're sent. Contract-preserving and
fail-open: anything unexpected leaves the original call untouched. Reductions are
deterministic, so the prompt-cache prefix stays stable.
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


def wrap_gemini(client: Any, **opts) -> Any:
    """Reduce functionResponse tool outputs on a google-genai client's generate_content."""
    try:
        models = client.models
        models.generate_content = wrap_messages_create(
            models.generate_content, fmt="gemini", opts=opts, key="contents"
        )
    except Exception:
        pass  # fail open
    return client


def looks_like_openai(obj: Any) -> bool:
    return hasattr(obj, "chat") and hasattr(obj.chat, "completions")


def looks_like_anthropic(obj: Any) -> bool:
    return hasattr(obj, "messages") and hasattr(obj.messages, "create") \
        and not looks_like_openai(obj)


def looks_like_gemini(obj: Any) -> bool:
    return hasattr(obj, "models") and hasattr(obj.models, "generate_content")
