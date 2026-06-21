"""Anthropic provider-native interop — the headline differentiator.

LeanContext compresses tool outputs *by content* on the way in. Anthropic's native
context editing clears old tool results *by age* once the window grows. They are
complementary, and this module makes them run **together** on one client:

    from leancontext.integrations.anthropic_native import wrap_anthropic_native
    client = wrap_anthropic_native(anthropic.Anthropic(),
                                   trigger_input_tokens=30000, keep_tool_uses=3)
    # every messages.create now: (1) LeanContext-reduces tool_result blocks,
    #                            (2) enables clear_tool_uses_20250919,
    #                            (3) sends the context-management beta header.

Schema verified against platform.claude.com/docs (context-editing), 2026-06.
"""

from __future__ import annotations

import functools
from typing import Any, Iterable, Optional

from ..messages import reduce_messages

#: Beta header required to enable context management on the Messages API.
BETA_HEADER = "context-management-2025-06-27"

#: Tool-result clearing strategy identifier (verbatim from the API).
CLEAR_TOOL_USES = "clear_tool_uses_20250919"


def context_management(
    *,
    trigger_input_tokens: Optional[int] = None,
    keep_tool_uses: Optional[int] = None,
    clear_at_least_input_tokens: Optional[int] = None,
    exclude_tools: Optional[Iterable[str]] = None,
    clear_tool_inputs: Optional[bool] = None,
) -> dict:
    """Build the ``context_management`` request param for tool-result clearing.

    Omitted fields fall back to the API defaults. With no args this returns the
    minimal ``{"edits": [{"type": "clear_tool_uses_20250919"}]}``.
    """
    edit: dict[str, Any] = {"type": CLEAR_TOOL_USES}
    if trigger_input_tokens is not None:
        edit["trigger"] = {"type": "input_tokens", "value": int(trigger_input_tokens)}
    if keep_tool_uses is not None:
        edit["keep"] = {"type": "tool_uses", "value": int(keep_tool_uses)}
    if clear_at_least_input_tokens is not None:
        edit["clear_at_least"] = {"type": "input_tokens", "value": int(clear_at_least_input_tokens)}
    if exclude_tools is not None:
        edit["exclude_tools"] = list(exclude_tools)
    if clear_tool_inputs is not None:
        edit["clear_tool_inputs"] = bool(clear_tool_inputs)
    return {"edits": [edit]}


def beta_headers(extra: Optional[dict] = None) -> dict:
    """Return headers enabling context management, merged with ``extra``."""
    headers = dict(extra or {})
    headers.setdefault("anthropic-beta", BETA_HEADER)
    return headers


def wrap_anthropic_native(client: Any, *, reduce: bool = True, send_beta: bool = True, **cm) -> Any:
    """Wrap an Anthropic client so messages.create composes reduction + native clearing.

    ``cm`` kwargs are forwarded to :func:`context_management`. Fail-open: any error
    leaves the original call untouched.
    """
    cm_config = context_management(**cm)

    try:
        orig = client.messages.create
    except Exception:
        return client

    if getattr(orig, "__leancontext_wrapped__", False):
        return client

    @functools.wraps(orig)
    def create(*args, **kwargs):
        try:
            if reduce and "messages" in kwargs:
                kwargs["messages"] = reduce_messages(kwargs["messages"], fmt="anthropic")
            kwargs.setdefault("context_management", cm_config)
            if send_beta:
                kwargs["extra_headers"] = beta_headers(kwargs.get("extra_headers"))
        except Exception:
            pass  # fail open
        return orig(*args, **kwargs)

    create.__leancontext_wrapped__ = True  # type: ignore[attr-defined]
    client.messages.create = create
    return client
