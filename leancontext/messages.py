"""Protocol-aware message reduction — the gateway/wire surface.

This is how LeanContext plugs into gateways (LiteLLM), SDK client wrappers, and proxies
*without* the structure-blindness that hurts wire-level compressors: the chat protocols
already tag tool outputs, so we find and reduce exactly those and nothing else. We never
touch system/user/assistant instruction text. Fail-open throughout.

Each provider format registers a detector and a per-item reducer in ``_FORMATS`` (like the
typed-reducer registry), so adding a format means adding one entry. Supported: OpenAI
chat-completions, Anthropic messages, Gemini contents, and the OpenAI Responses API.

Cache-safety: reductions are deterministic and content-addressed, so the same tool output
always serialises to the same bytes → the provider prompt-cache keeps hitting.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .core import reduce_text


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


# --- Gemini format -----------------------------------------------------------
# Gemini uses `contents` -> `parts`, where a tool result is a `functionResponse`
# part whose `response` is a dict. We reduce the large string values inside that
# dict, keeping the dict shape Gemini requires. Typed SDK objects pass through.

def _reduce_gemini_message(content: Any, opts: dict) -> Any:
    if not isinstance(content, dict) or not isinstance(content.get("parts"), list):
        return content
    new_parts, changed = [], False
    for part in content["parts"]:
        fr = part.get("functionResponse") if isinstance(part, dict) else None
        resp = fr.get("response") if isinstance(fr, dict) else None
        if isinstance(fr, dict) and isinstance(resp, dict):
            reduced = {k: (_reduce_str(v, opts) if isinstance(v, str) else v) for k, v in resp.items()}
            new_parts.append({**part, "functionResponse": {**fr, "response": reduced}})
            changed = True
        else:
            new_parts.append(part)
    if not changed:
        return content
    return {**content, "parts": new_parts}


# --- OpenAI Responses API format ---------------------------------------------
# The Responses API uses `input` (not `messages`); a tool result is an item with
# type "function_call_output" whose `output` is a string.

def _reduce_responses_message(item: Any, opts: dict) -> Any:
    if (
        isinstance(item, dict)
        and item.get("type") == "function_call_output"
        and isinstance(item.get("output"), str)
    ):
        new_item = dict(item)
        new_item["output"] = _reduce_str(item["output"], opts)
        return new_item
    return item


# --- format registry ---------------------------------------------------------

def _is_responses(m: dict) -> bool:
    return m.get("type") == "function_call_output"


def _is_gemini(m: dict) -> bool:
    return isinstance(m.get("parts"), list)


def _is_openai(m: dict) -> bool:
    return m.get("role") in ("tool", "function")


def _is_anthropic(m: dict) -> bool:
    content = m.get("content")
    return isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
    )


@dataclass(frozen=True)
class _Format:
    name: str
    detect: Callable[[dict], bool]
    reduce: Callable[[Any, dict], Any]
    priority: int


# Detection runs in priority order; the first format any single message matches wins.
_FORMATS: list[_Format] = sorted(
    [
        _Format("responses", _is_responses, _reduce_responses_message, 10),
        _Format("gemini", _is_gemini, _reduce_gemini_message, 20),
        _Format("openai", _is_openai, _reduce_openai_message, 30),
        _Format("anthropic", _is_anthropic, _reduce_anthropic_message, 40),
    ],
    key=lambda f: f.priority,
)
_REDUCE_BY_NAME = {f.name: f.reduce for f in _FORMATS}


# --- public ------------------------------------------------------------------

def detect_format(messages: list) -> str:
    """Best-effort detection of the message protocol; defaults to ``openai``."""
    for m in messages:
        if not isinstance(m, dict):
            continue
        for fmt in _FORMATS:
            if fmt.detect(m):
                return fmt.name
    return "openai"


def reduce_messages(messages: Any, *, fmt: str = "auto", **opts) -> Any:
    """Return a new message list with tool outputs reduced. Input is not mutated.

    Handles OpenAI (chat + Responses), Anthropic, and Gemini formats. Only tool-result
    content is touched; instructions are never altered. Anything unrecognised passes
    through unchanged (fail open).
    """
    if not isinstance(messages, list):
        return messages
    resolved = detect_format(messages) if fmt == "auto" else fmt
    reducer = _REDUCE_BY_NAME.get(resolved, _reduce_openai_message)
    return [reducer(m, opts) for m in messages]
