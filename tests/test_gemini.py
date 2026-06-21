import leancontext
from leancontext import reduce_messages
from leancontext.integrations.clients import wrap_gemini


def _big_log(n=300):
    lines = [f"2026-06-21T09:00:{i % 60:02d}.000Z INFO [worker] job={i} status=ok ms={i % 50}" for i in range(n)]
    lines.insert(150, "2026-06-21T09:05:00.000Z FATAL [render] OOM killed worker=7 — root cause")
    return "\n".join(lines)


def _gemini_contents():
    return [
        {"role": "user", "parts": [{"text": "why did it crash?"}]},
        {"role": "user", "parts": [
            {"functionResponse": {"name": "search_logs", "response": {"result": _big_log()}}},
        ]},
    ]


def test_gemini_format_autodetected():
    from leancontext import detect_format
    assert detect_format(_gemini_contents()) == "gemini"


def test_gemini_reduces_function_response_keeps_dict_shape():
    out = reduce_messages(_gemini_contents())  # auto -> gemini
    # user text part untouched
    assert out[0]["parts"][0]["text"] == "why did it crash?"
    resp = out[1]["parts"][0]["functionResponse"]["response"]
    assert isinstance(resp, dict)                      # dict contract preserved
    assert len(resp["result"]) < len(_big_log())       # value reduced
    assert "root cause" in resp["result"]              # signal preserved


def test_gemini_small_response_passes_through():
    contents = [{"role": "user", "parts": [
        {"functionResponse": {"name": "weather", "response": {"temp": "15C"}}},
    ]}]
    out = reduce_messages(contents, fmt="gemini")
    assert out[0]["parts"][0]["functionResponse"]["response"]["temp"] == "15C"


def test_wrap_gemini_client_reduces_contents():
    # Fake google-genai-style client; no SDK / network needed.
    class Models:
        def generate_content(self, **kw):
            self.captured = kw
            return "OK"

    class Client:
        def __init__(self):
            self.models = Models()

    client = Client()
    wrap_gemini(client)
    client.models.generate_content(model="gemini-3.5-flash", contents=_gemini_contents())
    resp = client.models.captured["contents"][1]["parts"][0]["functionResponse"]["response"]
    assert len(resp["result"]) < len(_big_log()) and "root cause" in resp["result"]


def test_generic_wrap_detects_gemini():
    class Models:
        def generate_content(self, **kw):
            self.captured = kw
            return "OK"

    class Client:
        def __init__(self):
            self.models = Models()

    client = leancontext.wrap(Client())
    client.models.generate_content(contents=_gemini_contents())
    resp = client.models.captured["contents"][1]["parts"][0]["functionResponse"]["response"]
    assert len(resp["result"]) < len(_big_log())
