import leancontext
from leancontext.tokens import active_tokenizer


def test_count_tokens_is_positive():
    assert leancontext.count_tokens("hello world, this is a bit of text") > 0


def test_custom_counter_overrides_then_resets():
    leancontext.set_token_counter(lambda _t: 42)
    try:
        assert leancontext.count_tokens("anything") == 42
        assert active_tokenizer() == "custom"
    finally:
        leancontext.set_token_counter(None)      # back to auto-detection
    assert leancontext.count_tokens("anything") != 42


def test_active_tokenizer_reports_a_name():
    leancontext.set_token_counter(None)
    name = active_tokenizer()
    assert isinstance(name, str) and name and name != "unresolved"
