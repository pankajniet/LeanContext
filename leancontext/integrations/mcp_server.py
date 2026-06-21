"""MCP server: expose LeanContext as tools any MCP client can call.

Three tools:
- ``reduce``  : shrink a tool-output payload to its signal, return the text.
- ``expand``  : fetch the original content behind a paging reference (lc://<id>).
- ``stats``   : report what a reduction would save, without changing anything.

The handlers below are plain functions (easy to test). ``mcp`` is imported lazily
inside ``create_server`` so this module stays import-safe without the ``mcp`` extra.

Run it::

    pip install "leancontext[mcp]"
    python -m leancontext.integrations.mcp_server      # serves over stdio
"""

from __future__ import annotations

from typing import Any

import leancontext
from leancontext import paging


def reduce(text: str, kind: str = "auto") -> str:
    """Reduce a tool-output payload (log, json, diff, stack trace, html, table)."""
    return leancontext.reduce(text, kind=kind).text


def expand(ref: str) -> str:
    """Return the original content for a LeanContext reference like 'lc://a1b2c3d4'."""
    original = paging.expand(ref)
    return original if original is not None else f"No content found for ref {ref!r}."


def stats(text: str, kind: str = "auto") -> dict[str, Any]:
    """Report what reducing ``text`` would save, without changing it."""
    r = leancontext.reduce(text, kind=kind)
    return {
        "kind": r.kind,
        "tokens_before": r.tokens_before,
        "tokens_after": r.tokens_after,
        "ratio": round(r.ratio, 4),
        "fidelity": round(r.fidelity, 4),
    }


def create_server(name: str = "leancontext"):
    """Build an MCP server exposing the tools above. Requires the ``mcp`` extra."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(name)
    server.tool()(reduce)
    server.tool()(expand)
    server.tool()(stats)
    return server


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
