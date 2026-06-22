import leancontext

# --- diff --------------------------------------------------------------------

def _diff():
    ctx = "\n".join(f" context line {i}" for i in range(40))
    return ("diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n"
            "@@ -1,42 +1,42 @@\n" + ctx + "\n-old broken line\n+new fixed line\n" + ctx)


def test_diff_keeps_changes_collapses_context():
    r = leancontext.reduce(_diff())
    assert r.kind == "diff"
    assert "-old broken line" in r.text and "+new fixed line" in r.text
    assert "@@ -1,42 +1,42 @@" in r.text
    assert "unchanged lines" in r.text
    assert r.tokens_after < r.tokens_before


def test_diff_detection_ignores_hunk_shaped_prose():
    from leancontext.reducers.diff import _detect

    # A hunk-shaped line inside prose, with no real +/- change lines: must NOT be
    # treated as a diff (else the context-collapsing reducer would drop prose lines).
    prose = (
        "Release notes for the range @@ -1,2 +3,4 @@ in the spec.\n"
        "This paragraph explains the change in plain words.\n"
        "It spans several lines of ordinary text.\n"
        "None of which are diff change lines."
    )
    assert _detect(prose) is False
    # a genuine hunk with change lines is still detected
    assert _detect("@@ -1,2 +1,2 @@\n context\n-old\n+new") is True


# --- stacktrace --------------------------------------------------------------

def _trace(n=30):
    frames = "\n".join(f'  File "mod{i}.py", line {i}, in func{i}\n    do_something({i})' for i in range(n))
    return "Traceback (most recent call last):\n" + frames + "\nValueError: boom — root cause here"


def test_stacktrace_keeps_exception_collapses_middle():
    r = leancontext.reduce(_trace())
    assert r.kind == "stacktrace"
    assert "ValueError: boom — root cause here" in r.text   # exception preserved
    assert "stack frames hidden" in r.text
    assert r.tokens_after < r.tokens_before


def test_stacktrace_short_passes_through_safely():
    short = 'Traceback (most recent call last):\n  File "a.py", line 1, in x\n    boom()\nKeyError: 1'
    r = leancontext.reduce(short)
    # too small to bother / nothing to collapse -> safe no-op, original intact
    assert "KeyError: 1" in r.text


# --- html --------------------------------------------------------------------

def _html():
    items = "".join(f"<li>item {i}</li>" for i in range(80))
    return ("<!doctype html><html><head><title>T</title><style>.x{color:red}</style>"
            "<script>var a=1;" + ("x" * 300) + "</script></head><body>"
            "<h1>Incident Report</h1><ul>" + items + "</ul>"
            "<a href='https://example.com/page'>details</a></body></html>")


def test_html_strips_tags_keeps_text_and_links():
    r = leancontext.reduce(_html())
    assert r.kind == "html"
    assert "Incident Report" in r.text and "item 1" in r.text
    assert "https://example.com/page" in r.text       # links preserved
    assert "<script" not in r.text and "<li>" not in r.text
    assert r.tokens_after < r.tokens_before


def test_determinism_across_new_reducers():
    for payload in (_diff(), _trace(), _html()):
        assert leancontext.reduce(payload).text == leancontext.reduce(payload).text
