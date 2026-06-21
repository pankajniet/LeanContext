import leancontext
from leancontext import reduce_messages


def _log(n=400):
    lines = [f"2026-06-21T09:00:{i % 60:02d}.000Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(200, "2026-06-21T09:05:00.000Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


def test_openai_tool_message_reduced_instructions_untouched():
    system = {"role": "system", "content": "You are a helpful agent. Follow the rules exactly."}
    user = {"role": "user", "content": "why did it crash?"}
    tool = {"role": "tool", "tool_call_id": "c1", "content": _log()}
    out = reduce_messages([system, user, tool])

    assert out[0] == system                     # instructions never touched
    assert out[1] == user
    assert len(out[2]["content"]) < len(tool["content"])  # tool output shrank
    assert "root cause" in out[2]["content"]    # signal preserved


def test_anthropic_tool_result_reduced():
    msgs = [
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": _log()},
        ]},
    ]
    out = reduce_messages(msgs, fmt="anthropic")
    reduced = out[0]["content"][0]["content"]
    assert len(reduced) < len(_log())
    assert "root cause" in reduced


def test_anthropic_text_block_tool_result():
    msgs = [
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1",
             "content": [{"type": "text", "text": _log()}]},
        ]},
    ]
    out = reduce_messages(msgs)  # auto-detect anthropic via tool_result block
    reduced = out[0]["content"][0]["content"][0]["text"]
    assert "root cause" in reduced and len(reduced) < len(_log())


def test_input_not_mutated():
    tool = {"role": "tool", "content": _log()}
    msgs = [tool]
    before = tool["content"]
    reduce_messages(msgs)
    assert tool["content"] == before            # original list/dicts untouched


def test_non_list_passthrough():
    assert reduce_messages("not a list") == "not a list"


def test_kill_switch_applies_to_messages():
    tool = {"role": "tool", "content": _log()}
    leancontext.disable()
    try:
        out = reduce_messages([tool])
        assert out[0]["content"] == tool["content"]   # no-op when disabled
    finally:
        leancontext.enable()
