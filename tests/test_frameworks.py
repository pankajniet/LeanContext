import asyncio

import pytest

import leancontext


def _log(n=400):
    lines = [f"2026-06-21T09:00:{i % 60:02d}Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(200, "2026-06-21T09:05:00Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


def test_langchain_tool_reduced_in_place():
    pytest.importorskip("langchain_core")
    from langchain_core.tools import tool

    @tool
    def search(q: str) -> str:
        """Search the logs."""
        return _log()

    wrapped = leancontext.wrap(search)
    assert type(wrapped).__name__ == "StructuredTool"      # schema/object preserved
    assert wrapped.name == "search"
    out = wrapped.invoke({"q": "errors"})
    assert "root cause" in out and len(out) < len(_log())   # output reduced


def test_agno_tool_reduced_in_place():
    pytest.importorskip("agno")
    from agno.tools import tool

    def fetch(q: str) -> str:
        """Fetch logs."""
        return _log()

    fn = tool(fetch)                       # -> agno Function
    wrapped = leancontext.wrap(fn)
    assert type(wrapped).__name__ == "Function"
    out = wrapped.entrypoint("errors")
    assert "root cause" in out and len(out) < len(_log())


def test_wrap_list_of_framework_tools():
    pytest.importorskip("langchain_core")
    from langchain_core.tools import tool

    @tool
    def a(q: str) -> str:
        """A."""
        return _log()

    @tool
    def b(q: str) -> str:
        """B."""
        return _log()

    tools = leancontext.wrap([a, b])
    assert all(type(t).__name__ == "StructuredTool" for t in tools)
    assert "root cause" in tools[0].invoke({"q": "x"})


def test_async_tool_function_reduced():
    @leancontext.reduce
    async def fetch(q: str) -> str:
        return _log()

    out = asyncio.run(fetch("errors"))
    assert "root cause" in out and len(out) < len(_log())


def test_generic_tool_object_shapes_wrapped_in_place():
    # Frameworks expose the tool callable on different attributes; wrap() handles them.
    class FnTool:        # LlamaIndex-style .fn
        def __init__(self):
            self.fn = lambda **_: _log()

    class FunctionTool:  # Pydantic-AI-style .function
        def __init__(self):
            self.function = lambda **_: _log()

    for obj, attr in ((FnTool(), "fn"), (FunctionTool(), "function")):
        wrapped = leancontext.wrap(obj)
        out = getattr(wrapped, attr)()
        assert "root cause" in out and len(out) < len(_log())


def test_async_on_invoke_tool_shape():
    class AgentTool:     # OpenAI Agents SDK-style async .on_invoke_tool
        async def on_invoke_tool(self, ctx=None, args=None) -> str:
            return _log()

    obj = AgentTool()
    obj.on_invoke_tool = leancontext.integrations.wrap_callable(obj.on_invoke_tool)
    out = asyncio.run(obj.on_invoke_tool())
    assert "root cause" in out and len(out) < len(_log())
