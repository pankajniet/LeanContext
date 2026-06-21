"""Run LeanContext's reduction alongside Anthropic's native context editing.

LeanContext reduces tool outputs by content on the way in; Anthropic's context
editing clears old tool results by age as the window grows. They're complementary,
and this module turns both on for one client:

    from leancontext.integrations.anthropic_native import wrap_anthropic_native
    client = wrap_anthropic_native(anthropic.Anthropic(),
                                   trigger_input_tokens=30000, keep_tool_uses=3)
    # every messages.create now: (1) LeanContext-reduces tool_result blocks,
    #                            (2) enables clear_tool_uses_20250919,
    #                            (3) sends the context-management beta header.

Schema verified against platform.claude.com/docs (context-editing), 2026-06.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ._common import wrap_messages_create

#: Beta header required to enable context management on the Messages API.
BETA_HEADER = "context-management-2025-06-27"

#: Tool-result clearing strategy identifier (verbatim from the API).
CLEAR_TOOL_USES = "clear_tool_uses_20250919"


def context_management(
    *,
    trigger_input_tokens: int | None = None,
    keep_tool_uses: int | None = None,
    clear_at_least_input_tokens: int | None = None,
    exclude_tools: Iterable[str] | None = None,
    clear_tool_inputs: bool | None = None,
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


def beta_headers(extra: dict | None = None) -> dict:
    """Return headers enabling context management, merged with ``extra``."""
    headers = dict(extra or {})
    headers.setdefault("anthropic-beta", BETA_HEADER)
    return headers


def wrap_anthropic_native(client: Any, *, reduce: bool = True, send_beta: bool = True, **cm) -> Any:
    """Wrap an Anthropic client so messages.create composes reduction + native clearing.

    ``cm`` kwargs are forwarded to :func:`context_management`. Fail-open.
    """
    cm_config = context_management(**cm)

    def inject(kwargs: dict) -> None:
        kwargs.setdefault("context_management", cm_config)
        if send_beta:
            kwargs["extra_headers"] = beta_headers(kwargs.get("extra_headers"))

    try:
        client.messages.create = wrap_messages_create(
            client.messages.create, fmt="anthropic", opts={}, reduce=reduce, before=inject
        )
    except Exception:
        pass  # fail open
    return client
