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

    import leancontext.integrations.litellm as ll
    ll.patch()                      # reduce messages on every litellm.completion call
"""

from __future__ import annotations

import functools

from ._common import mark, reduce_messages_in, wrap_messages_create

_REDUCIBLE_CALLS = ("completion", "text_completion")


def make_handler(**opts):
    """Build a LiteLLM proxy callback that reduces tool outputs before each call."""
    from litellm.integrations.custom_logger import CustomLogger  # optional dependency

    class LeanContextHandler(CustomLogger):
        async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
            if call_type in _REDUCIBLE_CALLS:
                # key=None: reduce chat (messages) or Responses (input) payloads alike
                reduce_messages_in(data, "auto", opts, key=None)  # fail-open in-place
            return data

    return LeanContextHandler()


def patch(**opts) -> None:
    """Monkeypatch ``litellm.completion``/``acompletion`` to reduce messages. Idempotent."""
    import litellm

    if getattr(litellm, "_leancontext_patched", False):
        return

    litellm.completion = wrap_messages_create(litellm.completion, fmt="auto", opts=opts, key=None)

    if hasattr(litellm, "acompletion"):
        _orig_acompletion = litellm.acompletion

        @functools.wraps(_orig_acompletion)
        async def acompletion(*args, **kwargs):
            reduce_messages_in(kwargs, "auto", opts, key=None)
            return await _orig_acompletion(*args, **kwargs)

        litellm.acompletion = mark(acompletion)

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
