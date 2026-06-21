"""LiteLLM integration — gateway/proxy and SDK.

Verified against LiteLLM docs (docs.litellm.ai/docs/proxy/call_hooks):
a proxy callback subclasses ``CustomLogger`` and implements
``async_pre_call_hook(self, user_api_key_dict, cache, data, call_type)``,
mutates ``data["messages"]``, and returns ``data``.

Nothing here is imported by ``leancontext`` at package load — ``litellm`` stays an
optional dependency. Import this module explicitly only when you use LiteLLM.

Proxy usage (config.yaml)::

    litellm_settings:
      callbacks: leancontext.integrations.litellm.proxy_handler_instance

SDK usage::

    import leancontext.integrations.litellm as wl
    wl.patch()                      # reduce messages on every litellm.completion call
"""

from __future__ import annotations

import functools

from ..messages import reduce_messages

_REDUCIBLE_CALLS = ("completion", "text_completion")


def make_handler(**opts):
    """Build a LiteLLM proxy callback that reduces tool outputs before each call."""
    from litellm.integrations.custom_logger import CustomLogger  # optional dependency

    class LeanContextHandler(CustomLogger):
        async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
            if call_type in _REDUCIBLE_CALLS and isinstance(data, dict) and "messages" in data:
                try:
                    data["messages"] = reduce_messages(data["messages"], **opts)
                except Exception:
                    pass  # fail open — never break the proxy
            return data

    return LeanContextHandler()


def patch(**opts) -> None:
    """Monkeypatch ``litellm.completion``/``acompletion`` to reduce messages. Idempotent."""
    import litellm

    if getattr(litellm, "_leancontext_patched", False):
        return

    _orig_completion = litellm.completion

    @functools.wraps(_orig_completion)
    def completion(*args, **kwargs):
        if "messages" in kwargs:
            try:
                kwargs["messages"] = reduce_messages(kwargs["messages"], **opts)
            except Exception:
                pass
        return _orig_completion(*args, **kwargs)

    litellm.completion = completion

    if hasattr(litellm, "acompletion"):
        _orig_acompletion = litellm.acompletion

        @functools.wraps(_orig_acompletion)
        async def acompletion(*args, **kwargs):
            if "messages" in kwargs:
                try:
                    kwargs["messages"] = reduce_messages(kwargs["messages"], **opts)
                except Exception:
                    pass
            return await _orig_acompletion(*args, **kwargs)

        litellm.acompletion = acompletion

    litellm._leancontext_patched = True


def unpatch() -> None:
    import litellm

    for name in ("completion", "acompletion"):
        fn = getattr(litellm, name, None)
        orig = getattr(fn, "__wrapped__", None)
        if orig is not None:
            setattr(litellm, name, orig)
    litellm._leancontext_patched = False


try:  # convenience instance for config.yaml; only built if litellm is installed
    proxy_handler_instance = make_handler()
except Exception:  # pragma: no cover - litellm not installed
    proxy_handler_instance = None
