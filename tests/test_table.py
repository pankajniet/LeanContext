import leancontext


def _kubectl(rows=15):
    head = "NAME                 READY   STATUS      RESTARTS   AGE"
    lines = [head]
    for i in range(rows):
        status = "Running" if i % 4 else "Pending"
        lines.append(f"service-pod-{i:<4}     1/1     {status:<10}  {i % 3}          {i}d")
    return "\n".join(lines)


def test_table_collapses_padding_keeps_values():
    r = leancontext.reduce(_kubectl())
    assert r.kind == "table"
    assert r.tokens_after < r.tokens_before
    # every value still present after padding is collapsed
    for value in ["service-pod-0", "Running", "Pending", "READY", "STATUS"]:
        assert value in r.text
    assert "  " not in r.text          # no double-spaces left


def test_table_is_deterministic():
    payload = _kubectl()
    assert leancontext.reduce(payload).text == leancontext.reduce(payload).text


def test_prose_is_not_treated_as_table():
    prose = "\n".join(
        "This is an ordinary sentence of prose without any aligned columns." for _ in range(8)
    )
    assert leancontext.reduce(prose).kind != "table"
