"""Framework-agnostic integration surfaces.

These never change a tool's contract: a tool that returns ``str`` still returns
``str``; anything non-string is passed through untouched. The agent cannot tell
LeanContext is present. See AGENTS.md §5B/§5D.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from ..core import reduce_text
from ._common import is_wrapped, mark


def _reduced(result: Any, opts: dict) -> Any:
    return reduce_text(result, **opts).text if isinstance(result, str) else result


def wrap_callable(fn: Callable, **opts) -> Callable:
    """Wrap a tool callable so its string return value is reduced at the source.

    Works for sync and async tools; non-string returns pass through untouched.
    """
    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def awrapper(*args, **kwargs):
            return _reduced(await fn(*args, **kwargs), opts)

        return mark(awrapper)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return _reduced(fn(*args, **kwargs), opts)

    return mark(wrapper)


def wrap(target: Any, **opts) -> Any:
    """Best-effort universal wrap.

    Accepts a plain callable, a list/tuple of tools, an OpenAI/Anthropic SDK client,
    or a framework tool object exposing its callable on a known attribute. Anything
    it doesn't recognise is returned unchanged — fail open.
    """
    if isinstance(target, (list, tuple)):
        return type(target)(wrap(t, **opts) for t in target)

    # Framework tool objects first. Several are callable themselves, so they must
    # be wrapped in place (keeping their schema) before the plain-callable path.
    try:
        from .frameworks import (
            looks_like_agno_tool,
            looks_like_langchain_tool,
            wrap_agno,
            wrap_langchain,
        )

        if looks_like_langchain_tool(target):
            return wrap_langchain(target, **opts)
        if looks_like_agno_tool(target):
            return wrap_agno(target, **opts)
    except Exception:
        pass  # fail open

    # SDK clients (OpenAI / Anthropic / Gemini): reduce messages on the call.
    try:
        from .clients import (
            looks_like_anthropic,
            looks_like_gemini,
            looks_like_openai,
            wrap_anthropic,
            wrap_gemini,
            wrap_openai,
        )

        if looks_like_openai(target):
            return wrap_openai(target, **opts)
        if looks_like_anthropic(target):
            return wrap_anthropic(target, **opts)
        if looks_like_gemini(target):
            return wrap_gemini(target, **opts)
    except Exception:
        pass  # fail open

    # Plain callable tools.
    if callable(target) and not isinstance(target, type):
        return target if is_wrapped(target) else wrap_callable(target, **opts)

    # Fallback for other tool objects: wrap the user callable in place. These are
    # the attribute names frameworks expose their tool function on (LlamaIndex .fn,
    # Pydantic AI .function, OpenAI Agents SDK .on_invoke_tool, etc.).
    for attr in ("func", "coroutine", "entrypoint", "fn", "function", "on_invoke_tool"):
        inner = getattr(target, attr, None)
        if callable(inner) and not is_wrapped(inner):
            try:
                setattr(target, attr, wrap_callable(inner, **opts))
            except Exception:
                pass  # immutable attr -> leave as-is (fail open)
    return target
