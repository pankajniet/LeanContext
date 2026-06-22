import json

from leancontext.fidelity import fidelity_score


def test_json_fidelity_full_when_values_preserved():
    records = [{"id": i, "name": f"user-{i}", "score": i + 0.5} for i in range(20)]
    original = json.dumps(records)
    # columnar form keeps every value, just drops repeated keys
    reduced = "fields: id | name | score\n" + "\n".join(
        f"{r['id']} | {r['name']} | {r['score']}" for r in records
    )
    assert fidelity_score(original, reduced, "json") == 1.0


def test_json_fidelity_drops_when_value_lost():
    original = json.dumps([{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}])
    reduced = "id | name\n1 | alpha"          # 'beta' and '2' missing
    assert fidelity_score(original, reduced, "json") < 1.0


def test_diff_fidelity_requires_change_lines():
    original = "@@ -1,2 +1,2 @@\n context\n-old value\n+new value\n context"
    assert fidelity_score(original, "-old value\n+new value", "diff") == 1.0
    assert fidelity_score(original, "+new value", "diff") < 1.0   # dropped a change


def test_stacktrace_fidelity_requires_exception():
    original = 'Traceback (most recent call last):\n  File "a.py", line 1\nKeyError: 42'
    assert fidelity_score(original, "...\nKeyError: 42", "stacktrace") == 1.0
    assert fidelity_score(original, "...frames only...", "stacktrace") == 0.0


def test_unknown_kind_uses_signal_score():
    # no severity lines -> nothing critical -> 1.0
    assert fidelity_score("just some plain text", "plain text", "text") == 1.0


def test_html_fidelity_drops_when_visible_text_lost():
    # neutral prose (no severity keyword): a content-aware check must still see the loss
    html = "<html><body><h1>Welcome to the dashboard</h1><p>ordinary body paragraph</p></body></html>"
    assert fidelity_score(html, "Welcome to the dashboard\n\nordinary body paragraph", "html") == 1.0
    assert fidelity_score(html, "Welcome to the dashboard", "html") < 1.0   # body dropped
    assert fidelity_score(html, "", "html") < 1.0


def test_table_fidelity_drops_when_row_lost():
    original = "NAME   AGE\npod-a   1d\npod-b   2d\npod-c   3d"
    assert fidelity_score(original, "NAME AGE\npod-a 1d\npod-b 2d\npod-c 3d", "table") == 1.0
    assert fidelity_score(original, "NAME AGE\npod-a 1d\npod-c 3d", "table") < 1.0   # pod-b dropped
