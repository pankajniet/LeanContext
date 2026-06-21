"""Standalone OpenAI-compatible reducing proxy (FastAPI/ASGI).

The language-agnostic surface: point any client's ``base_url`` at this proxy and
tool outputs in ``messages`` are reduced before being forwarded upstream. Any
language, any framework, zero code change in the agent.

FastAPI is imported lazily inside ``create_app`` so this module stays import-safe
without the ``proxy`` extra.

    from leancontext.integrations.proxy import create_app
    app = create_app()                      # forwards to $LEANCONTEXT_UPSTREAM
    # uvicorn leancontext.integrations.proxy:app   (after `app = create_app()`)
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from ._common import reduce_messages_in


def _httpx_forwarder(upstream: str) -> Callable[[dict], Any]:
    def forward(payload: dict) -> Any:
        import httpx

        headers = {}
        key = os.environ.get("OPENAI_API_KEY")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        with httpx.Client(timeout=120) as client:
            resp = client.post(upstream.rstrip("/") + "/v1/chat/completions",
                               json=payload, headers=headers)
            return resp.json()

    return forward


def create_app(forwarder: Callable[[dict], Any] | None = None,
               upstream: str | None = None):
    """Build the FastAPI app. Pass a custom ``forwarder(payload)->dict`` for tests."""
    from fastapi import Body, FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="LeanContext proxy")
    forward = forwarder or _httpx_forwarder(
        upstream or os.environ.get("LEANCONTEXT_UPSTREAM", "https://api.openai.com")
    )

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    @app.post("/v1/chat/completions")
    async def chat_completions(payload: dict = Body(...)):
        reduce_messages_in(payload, "openai", {})  # fail-open, in-place
        result = forward(payload)
        if hasattr(result, "__await__"):
            result = await result
        return JSONResponse(result)

    return app
