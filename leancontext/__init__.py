"""LeanContext — keep agent context lean (drop redundant boilerplate, keep the signal).

Deterministic, type-aware reduction of agent tool outputs *at the source*.
Cut LLM token cost without making the agent do less.

Quick start::

    from leancontext import reduce

    # 1) manual
    payload = reduce(tool_output).text

    # 2) decorator (one line per tool)
    @reduce
    def search_logs(q: str) -> str:
        ...

    # 3) bulk wrap (one line for all tools, any framework)
    tools = reduce(tools)            # or leancontext.wrap(tools)
"""

from __future__ import annotations

from typing import Any

from .core import (
    CONFIG,
    Reduction,
    clear_cache,
    clear_reduction_hooks,
    detect_kind,
    disable,
    enable,
    is_disabled,
    on_reduction,
    reduce_text,
    remove_reduction_hook,
)
from .cost import CostTracker, estimate_savings, set_price
from .integrations import wrap, wrap_anthropic, wrap_callable, wrap_gemini, wrap_openai
from .messages import detect_format, reduce_messages
from .tokens import count_tokens, set_token_counter, use_tiktoken

__version__ = "0.0.1"

__all__ = [
    "reduce",
    "reduce_text",
    "reduce_messages",
    "detect_format",
    "Reduction",
    "wrap",
    "wrap_callable",
    "wrap_openai",
    "wrap_anthropic",
    "wrap_gemini",
    "detect_kind",
    "disable",
    "enable",
    "is_disabled",
    "on_reduction",
    "remove_reduction_hook",
    "clear_reduction_hooks",
    "clear_cache",
    "count_tokens",
    "set_token_counter",
    "use_tiktoken",
    "estimate_savings",
    "CostTracker",
    "set_price",
    "CONFIG",
    "__version__",
]


def reduce(content: Any = None, /, **opts) -> Any:
    """Polymorphic entry point.

    - ``reduce(text)`` -> :class:`Reduction`
    - ``reduce(callable)`` -> wrapped tool (decorator form: ``@reduce``)
    - ``reduce(list_of_tools)`` / ``reduce(tool_obj)`` -> wrapped tools
    - ``reduce(**opts)`` -> a decorator/partial carrying those options
    """
    if content is None:
        def deferred(target: Any) -> Any:
            return reduce(target, **opts)
        return deferred

    if isinstance(content, str):
        return reduce_text(content, **opts)

    # callable, tool, list of tools, or SDK client -> best-effort wrap (fail open)
    return wrap(content, **opts)
