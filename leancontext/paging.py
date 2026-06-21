"""Paging tier — flatten the quadratic for *aged* context.

Compression shrinks the per-turn constant; paging removes aged content from the wire
entirely. When the agent has moved on from a tool result, collapse it to a tiny
expandable reference (~tens of tokens) and stash the original in a content store the
agent can pull back on demand via the ``expand`` tool.

Refs are content hashes, so they're deterministic and re-derivable. The store is
in-memory by default, or disk-backed (under ``root``) for cross-process retrieval.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Optional

from .tokens import count_tokens

REF_SCHEME = "lc"
_REF_RE = re.compile(r"lc://([0-9a-f]{6,40})")


class ContentStore:
    """Maps a content hash → original content. In-memory, or disk-backed if ``root`` set."""

    def __init__(self, root: Optional[str] = None):
        self.root = root
        self._mem: dict[str, str] = {}
        if self.root:
            os.makedirs(self.root, exist_ok=True)

    def _path(self, ref: str) -> str:
        return os.path.join(self.root, f"{ref}.txt")  # type: ignore[arg-type]

    def put(self, content: str) -> str:
        ref = hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]
        if self.root:
            with open(self._path(ref), "w", encoding="utf-8") as fh:
                fh.write(content)
        else:
            self._mem[ref] = content
        return ref

    def get(self, ref: str) -> Optional[str]:
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


def store(content: str, using: Optional[ContentStore] = None) -> str:
    """Stash content and return its ref id."""
    return (using or _DEFAULT_STORE).put(content)


def expand(ref: str, using: Optional[ContentStore] = None) -> Optional[str]:
    """Return the original content for a ref (accepts 'lc://<id>' or a bare id)."""
    return (using or _DEFAULT_STORE).get(_normalize(ref))


def reference_line(content: str, summary: Optional[str] = None,
                   using: Optional[ContentStore] = None) -> str:
    """Stash content and return a compact, expandable reference line."""
    ref = store(content, using=using)
    tokens = count_tokens(content)
    tail = f" — {summary}" if summary else ""
    return f"[{REF_SCHEME}://{ref} · {tokens} tokens · call leancontext_expand to view{tail}]"


def page(content: str, *, summary: Optional[str] = None,
         using: Optional[ContentStore] = None) -> str:
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
            "ref": {"type": "string", "description": "The reference id, e.g. 'lc://a1b2c3d4' or the bare id."},
        },
        "required": ["ref"],
    },
}
