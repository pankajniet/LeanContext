"""Framework adapters: reduce a framework's tool outputs.

Each framework wraps a tool differently, and several tool objects are themselves
callable, so we wrap the underlying user function *in place* and return the same
object (keeping its name, schema, and metadata).

Covered:
- LangChain  (``StructuredTool``/``Tool`` via ``.func`` / ``.coroutine``)
- LangGraph  (uses LangChain tools, so the LangChain adapter applies)
- Agno       (``Function`` via ``.entrypoint``)

Plain functions don't need an adapter — ``leancontext.wrap`` / ``@reduce`` handle them.
"""

from __future__ import annotations

from typing import Any

from ._common import is_wrapped
from .decorator import wrap_callable


def _module_root(obj: Any) -> str:
    return type(obj).__module__.split(".")[0]


def looks_like_langchain_tool(obj: Any) -> bool:
    return _module_root(obj) in ("langchain", "langchain_core") and hasattr(obj, "func")


def looks_like_agno_tool(obj: Any) -> bool:
    return _module_root(obj) == "agno" and hasattr(obj, "entrypoint")


def _wrap_attr_in_place(obj: Any, attr: str, opts: dict) -> None:
    fn = getattr(obj, attr, None)
    if callable(fn) and not is_wrapped(fn):
        try:
            setattr(obj, attr, wrap_callable(fn, **opts))
        except Exception:
            pass  # immutable/validated field -> leave as-is (fail open)


def wrap_langchain(tool: Any, **opts) -> Any:
    """Reduce outputs of a LangChain or LangGraph tool, in place."""
    if isinstance(tool, (list, tuple)):
        return type(tool)(wrap_langchain(t, **opts) for t in tool)
    _wrap_attr_in_place(tool, "func", opts)
    _wrap_attr_in_place(tool, "coroutine", opts)
    return tool


def wrap_agno(tool: Any, **opts) -> Any:
    """Reduce outputs of an Agno tool (Function), in place."""
    if isinstance(tool, (list, tuple)):
        return type(tool)(wrap_agno(t, **opts) for t in tool)
    _wrap_attr_in_place(tool, "entrypoint", opts)
    return tool
