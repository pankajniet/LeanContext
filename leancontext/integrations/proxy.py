"""Standalone OpenAI-compatible reducing proxy (FastAPI/ASGI).

Point any client's ``base_url`` at this proxy and tool outputs in ``messages`` are
reduced before being forwarded upstream. Any language, any framework, no code change.

It forwards the caller's auth headers, supports streaming responses, and turns
upstream failures into a clean 502 instead of crashing. FastAPI is imported lazily
inside ``create_app`` so this module stays import-safe without the proxy extra.

    from leancontext.integrations.proxy import create_app
    app = create_app()                      # forwards to $LEANCONTEXT_UPSTREAM
    # uvicorn leancontext.integrations.proxy:app   (after `app = create_app()`)
"""

from __future__ import annotations

import inspect
import os
from collections.abc import Callable
from typing import Any

from ._common import reduce_messages_in

# Headers we pass through to the upstream provider (auth + provider version flags).
_FORWARD = ("authorization", "api-key", "x-api-key", "anthropic-version", "anthropic-beta")


def _forward_headers(request: Any) -> dict:
    """Carry the caller's auth/version headers upstream; fall back to OPENAI_API_KEY."""
    headers: dict[str, str] = {"content-type": "application/json"}
    if request is not None:
        for name in _FORWARD:
            value = request.headers.get(name)
            if value:
                headers[name] = value
    if not any(k.lower() == "authorization" for k in headers):
        key = os.environ.get("OPENAI_API_KEY")
        if key:
            headers["Authorization"] = f"Bearer {key}"
    return headers


def create_app(forwarder: Callable[[dict, dict], Any] | None = None,
               upstream: str | None = None):
    """Build the FastAPI app. Pass a custom ``forwarder(payload, headers)`` for tests."""
    from fastapi import Body, FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse

    # Make the string annotation `Request` resolvable under `from __future__ import annotations`.
    globals()["Request"] = Request

    app = FastAPI(title="LeanContext proxy")
    url = (upstream or os.environ.get("LEANCONTEXT_UPSTREAM", "https://api.openai.com")).rstrip("/")
    url += "/v1/chat/completions"

    def _httpx_forward(payload: dict, headers: dict) -> Any:
        import httpx

        if payload.get("stream"):
            def body():
                with httpx.stream("POST", url, json=payload, headers=headers, timeout=120) as resp:
                    yield from resp.iter_raw()
            return StreamingResponse(body(), media_type="text/event-stream")

        with httpx.Client(timeout=120) as client:
            resp = client.post(url, json=payload, headers=headers)
            return JSONResponse(resp.json(), status_code=resp.status_code)

    forward = forwarder or _httpx_forward

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request, payload: dict = Body(...)):
        reduce_messages_in(payload, "openai", {})  # fail-open, in-place
        try:
            result = forward(payload, _forward_headers(request))
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            return JSONResponse(
                {"error": {"message": str(exc), "type": "upstream_error"}}, status_code=502
            )
        if isinstance(result, (JSONResponse, StreamingResponse)):
            return result
        return JSONResponse(result)

    return app
