import json

from leancontext.fidelity import fidelity_score
from leancontext.reducers.json_data import reduce_json


def test_json_fidelity_full_when_values_preserved():
    records = [{"id": i, "name": f"user-{i}", "score": i + 0.5} for i in range(20)]
    original = json.dumps(records)
    # the real columnar form keeps every value, just drops the repeated keys
    reduced, _ = reduce_json(original)
    assert fidelity_score(original, reduced, "json") == 1.0


def test_json_fidelity_drops_when_value_lost():
    original = json.dumps([{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}])
    reduced = 'fields:["id","name"]\n[1,"alpha"]'   # second record (2 / "beta") dropped
    assert fidelity_score(original, reduced, "json") < 1.0


def test_json_fidelity_catches_substring_value_loss():
    # "1" and "10" are substrings of the surviving "100": a substring check would
    # wrongly call them preserved; whole-token multiset matching must not.
    original = json.dumps([{"id": "1"}, {"id": "10"}, {"id": "100"}])
    reduced = 'fields:["id"]\n["100"]'
    assert fidelity_score(original, reduced, "json") < 1.0


def test_diff_fidelity_requires_change_lines():
    original = "@@ -1,2 +1,2 @@\n context\n-old value\n+new value\n context"
    assert fidelity_score(original, "-old value\n+new value", "diff") == 1.0
    assert fidelity_score(original, "+new value", "diff") < 1.0   # dropped a change


def test_stacktrace_fidelity_requires_exception():
    original = 'Traceback (most recent call last):\n  File "a.py", line 1\nKeyError: 42'
    assert fidelity_score(original, "...\nKeyError: 42", "stacktrace") == 1.0
    assert fidelity_score(original, "...frames only...", "stacktrace") == 0.0


def test_stacktrace_fidelity_requires_all_chained_causes():
    # A chained traceback: dropping the earlier root cause / chain marker must score
    # below 1.0 (the old last-line-only check returned 1.0 and silently lost the cause).
    original = (
        'Traceback (most recent call last):\n  File "a.py", line 1, in f\n    f()\n'
        'ValueError: ORIGINAL ROOT CAUSE\n\n'
        'During handling of the above exception, another exception occurred:\n\n'
        'Traceback (most recent call last):\n  File "b.py", line 2, in g\n    g()\n'
        'RuntimeError: final'
    )
    # only the final exception survives -> the cause and the chain marker are lost
    assert fidelity_score(original, "...\nRuntimeError: final", "stacktrace") < 1.0
    # everything semantic preserved -> full score
    assert fidelity_score(original, original, "stacktrace") == 1.0


def test_unknown_kind_uses_signal_score():
    # no severity lines -> nothing critical -> 1.0
    assert fidelity_score("just some plain text", "plain text", "text") == 1.0


def test_html_fidelity_drops_when_visible_text_lost():
    # neutral prose (no severity keyword): a content-aware check must still see the loss
    html = "<html><body><h1>Welcome to the dashboard</h1><p>ordinary body paragraph</p></body></html>"
    assert fidelity_score(html, "Welcome to the dashboard\n\nordinary body paragraph", "html") == 1.0
    assert fidelity_score(html, "Welcome to the dashboard", "html") < 1.0   # body dropped
    assert fidelity_score(html, "", "html") < 1.0


def test_html_fidelity_not_inflated_by_common_words():
    # Many common words around two rare-but-important ones: dropping the rare words
    # must still trip the gate. A per-occurrence substring check scored this ~0.86
    # (above the 0.85 default) and let the loss through; distinct-word matching must not.
    html = (
        "<html><body><p>the cat sat on the mat in the house with the dog</p>"
        "<p>SECRET_TOKEN_XYZ unique_value_42</p></body></html>"
    )
    kept_all = "the cat sat on the mat in the house with the dog SECRET_TOKEN_XYZ unique_value_42"
    dropped_rare = "the cat sat on the mat in the house with the dog"
    assert fidelity_score(html, kept_all, "html") == 1.0
    assert fidelity_score(html, dropped_rare, "html") < 0.85   # below the default gate


def test_table_fidelity_drops_when_row_lost():
    original = "NAME   AGE\npod-a   1d\npod-b   2d\npod-c   3d"
    assert fidelity_score(original, "NAME AGE\npod-a 1d\npod-b 2d\npod-c 3d", "table") == 1.0
    assert fidelity_score(original, "NAME AGE\npod-a 1d\npod-c 3d", "table") < 1.0   # pod-b dropped
