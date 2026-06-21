"""Protocol-aware message reduction — the gateway/wire surface.

This is how LeanContext plugs into gateways (LiteLLM), SDK client wrappers, and proxies
*without* the structure-blindness that hurts wire-level compressors: the chat
protocols already tag tool outputs (OpenAI ``role="tool"``; Anthropic
``tool_result`` blocks), so we can find and reduce exactly those — and nothing
else. We never touch system/user/assistant instruction text. Fail-open throughout.

Cache-safety: reductions are deterministic and content-addressed, so the same tool
output always serialises to the same bytes → the provider prompt-cache keeps hitting.
"""

from __future__ import annotations

from typing import Any

from .core import reduce_text


def detect_format(messages: list) -> str:
    """Best-effort detection of the message protocol."""
    for m in messages:
        if not isinstance(m, dict):
            continue
        if m.get("role") in ("tool", "function"):
            return "openai"
        content = m.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    return "anthropic"
    return "openai"


def _reduce_str(text: Any, opts: dict) -> Any:
    if not isinstance(text, str):
        return text
    return reduce_text(text, **opts).text


# --- OpenAI / chat-completions format ----------------------------------------

def _reduce_openai_message(m: Any, opts: dict) -> Any:
    if not isinstance(m, dict) or m.get("role") not in ("tool", "function"):
        return m
    content = m.get("content")
    if isinstance(content, str):
        nm = dict(m)
        nm["content"] = _reduce_str(content, opts)
        return nm
    if isinstance(content, list):
        nm = dict(m)
        nm["content"] = [_reduce_openai_part(p, opts) for p in content]
        return nm
    return m


def _reduce_openai_part(part: Any, opts: dict) -> Any:
    if (
        isinstance(part, dict)
        and part.get("type") in ("text", "output_text")
        and isinstance(part.get("text"), str)
    ):
        np = dict(part)
        np["text"] = _reduce_str(part["text"], opts)
        return np
    return part


# --- Anthropic messages format -----------------------------------------------

def _reduce_anthropic_message(m: Any, opts: dict) -> Any:
    if not isinstance(m, dict):
        return m
    content = m.get("content")
    if not isinstance(content, list):
        return m
    new_blocks, changed = [], False
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            bc = block.get("content")
            if isinstance(bc, str):
                nb = dict(block)
                nb["content"] = _reduce_str(bc, opts)
                new_blocks.append(nb)
                changed = True
                continue
            if isinstance(bc, list):
                nb = dict(block)
                nb["content"] = [_reduce_anthropic_textblock(x, opts) for x in bc]
                new_blocks.append(nb)
                changed = True
                continue
        new_blocks.append(block)
    if not changed:
        return m
    nm = dict(m)
    nm["content"] = new_blocks
    return nm


def _reduce_anthropic_textblock(x: Any, opts: dict) -> Any:
    if isinstance(x, dict) and x.get("type") == "text" and isinstance(x.get("text"), str):
        nx = dict(x)
        nx["text"] = _reduce_str(x["text"], opts)
        return nx
    return x


# --- public ------------------------------------------------------------------

def reduce_messages(messages: Any, *, fmt: str = "auto", **opts) -> Any:
    """Return a new message list with tool outputs reduced. Input is not mutated.

    Only tool-result content is touched; instructions are never altered. Anything
    unrecognised passes through unchanged (fail open).
    """
    if not isinstance(messages, list):
        return messages
    resolved = detect_format(messages) if fmt == "auto" else fmt
    if resolved == "anthropic":
        return [_reduce_anthropic_message(m, opts) for m in messages]
    return [_reduce_openai_message(m, opts) for m in messages]
