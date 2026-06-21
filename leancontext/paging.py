"""Paging: drop aged tool outputs from the wire, keep them retrievable.

Reducing shrinks each payload; paging goes further by removing old payloads from
context once the agent has moved on. The output is replaced with a small reference
(a few tens of tokens) and the original is stored, so the agent can fetch it back
with the expand tool when it needs the detail again.

Refs are content hashes, so they're deterministic. The store is in-memory by
default, or disk-backed (set ``root``) for retrieval across processes.
"""

from __future__ import annotations

import os
import re

from .tokens import content_ref, count_tokens

REF_SCHEME = "lc"
_REF_RE = re.compile(r"lc://([0-9a-f]{6,40})")


class ContentStore:
    """Maps a content hash → original content. In-memory, or disk-backed if ``root`` set."""

    def __init__(self, root: str | None = None):
        self.root = root
        self._mem: dict[str, str] = {}
        if self.root:
            os.makedirs(self.root, exist_ok=True)

    def _path(self, ref: str) -> str:
        return os.path.join(self.root, f"{ref}.txt")  # type: ignore[arg-type]

    def put(self, content: str) -> str:
        ref = content_ref(content)
        if self.root:
            with open(self._path(ref), "w", encoding="utf-8") as fh:
                fh.write(content)
        else:
            self._mem[ref] = content
        return ref

    def get(self, ref: str) -> str | None:
        if self.root:
            try:
                with open(self._path(ref), encoding="utf-8") as fh:
                    return fh.read()
            except OSError:
                return None
        return self._mem.get(ref)


_DEFAULT_STORE = ContentStore()


def _normalize(ref: str) -> str:
    m = _REF_RE.search(ref)
    return m.group(1) if m else ref.strip()


def store(content: str, using: ContentStore | None = None) -> str:
    """Stash content and return its ref id."""
    return (using or _DEFAULT_STORE).put(content)


def expand(ref: str, using: ContentStore | None = None) -> str | None:
    """Return the original content for a ref (accepts 'lc://<id>' or a bare id)."""
    return (using or _DEFAULT_STORE).get(_normalize(ref))


def reference_line(content: str, summary: str | None = None,
                   using: ContentStore | None = None) -> str:
    """Stash content and return a compact, expandable reference line."""
    ref = store(content, using=using)
    tokens = count_tokens(content)
    tail = f" — {summary}" if summary else ""
    return f"[{REF_SCHEME}://{ref} · {tokens} tokens · call leancontext_expand to view{tail}]"


def page(content: str, *, summary: str | None = None,
         using: ContentStore | None = None) -> str:
    """Collapse aged content to an expandable reference (O(1) on the wire)."""
    return reference_line(content, summary=summary, using=using)


#: Tool spec to expose ``expand`` to an agent (OpenAI/Anthropic/MCP-compatible shape).
EXPAND_TOOL_SPEC = {
    "name": "leancontext_expand",
    "description": (
        "Retrieve the full original content for a LeanContext reference id "
        "(format: lc://<id>) that was collapsed to save tokens."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ref": {
                "type": "string",
                "description": "The reference id, e.g. 'lc://a1b2c3d4' or the bare id.",
            },
        },
        "required": ["ref"],
    },
}
