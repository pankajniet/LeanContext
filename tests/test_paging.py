import re

from leancontext import paging


def _content():
    return "incident log line\n" * 80 + "FATAL root cause\n"


def test_store_expand_roundtrip():
    c = _content()
    ref = paging.store(c)
    assert paging.expand(ref) == c
    assert paging.expand(f"lc://{ref}") == c          # accepts scheme prefix


def test_page_produces_compact_expandable_ref():
    c = _content()
    line = paging.page(c, summary="1 FATAL")
    assert "lc://" in line and "leancontext_expand" in line and "1 FATAL" in line
    assert len(line) < len(c)                          # the whole point: it's tiny
    ref = re.search(r"lc://([0-9a-f]+)", line).group(1)
    assert paging.expand(ref) == c                     # still fully recoverable


def test_refs_are_deterministic():
    c = _content()
    assert paging.store(c) == paging.store(c)          # content-addressed


def test_expand_unknown_returns_none():
    assert paging.expand("lc://deadbeef00") is None


def test_disk_backed_store(tmp_path):
    s = paging.ContentStore(root=str(tmp_path))
    ref = paging.store(_content(), using=s)
    # a fresh store pointed at the same dir can still retrieve it (cross-process)
    s2 = paging.ContentStore(root=str(tmp_path))
    assert paging.expand(ref, using=s2) == _content()


def test_expand_tool_spec_shape():
    spec = paging.EXPAND_TOOL_SPEC
    assert spec["name"] == "leancontext_expand"
    assert spec["input_schema"]["required"] == ["ref"]


def test_expand_rejects_path_traversal(tmp_path):
    store = paging.ContentStore(root=str(tmp_path))
    secret = tmp_path.parent / "leak.txt"
    secret.write_text("TOPSECRET")
    # refs that aren't content hashes must never resolve to a filesystem path
    for evil in ("../leak", "../../etc/hosts", "/etc/hosts", "..%2Fleak"):
        assert paging.expand(evil, using=store) is None
        assert store.get(evil) is None

