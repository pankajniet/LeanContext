"""Watch one tool call pass through LeanContext.

An agent is debugging a production incident. A log search returns thousands of
tokens of mostly-repeated lines, with one FATAL line buried in the middle that
explains the crash. LeanContext collapses the redundancy and keeps the signal.

Run:  python demo.py
"""

from __future__ import annotations

import leancontext


def build_incident_log() -> str:
    lines: list[str] = []
    # Routine, high-frequency noise: same handful of events, different values.
    for i in range(900):
        rid = f"{i:08x}-1c2d-4e5f-8a9b-0011223344{i % 100:02d}"
        ts = f"2026-06-21T09:{(i // 60) % 60:02d}:{i % 60:02d}.{i % 1000:03d}Z"
        if i % 7 == 0:
            lines.append(f'{ts} INFO  [gateway] request id={rid} path="/v1/render" status=200 ms={i % 80}')
        elif i % 7 == 3:
            lines.append(f'{ts} INFO  [cache] hit key="slide:{i}" region=us-east-1 ms={i % 12}')
        elif i % 7 == 5:
            lines.append(f'{ts} DEBUG [pool] checkout conn=0x{i:06x} idle={i % 30} active={i % 9}')
        else:
            lines.append(f'{ts} INFO  [worker] job={i} queue="render" attempts=1 ms={i % 200}')
    # A couple of warnings, and the one line that actually matters.
    lines.insert(420, "2026-06-21T09:07:00.012Z WARN  [pool] connection pool 90% saturated active=18 max=20")
    lines.insert(640, '2026-06-21T09:10:43.880Z FATAL [render] OOM killed worker=7 '
                      'rss=2147483648 limit=2147483648 doc="deck-8842" — crash root cause')
    return "\n".join(lines)


def show(title: str, payload: str) -> None:
    r = leancontext.reduce(payload)
    print(f"\n=== {title} ===")
    print(f"kind        : {r.kind}")
    print(f"tokens      : {r.tokens_before:>6} -> {r.tokens_after:<6}  ({r.ratio:.0%} saved)")
    print(f"fidelity    : {r.fidelity:.0%}")
    for note in r.notes:
        print(f"note        : {note}")
    fatal_in = "FATAL" in payload
    fatal_out = "crash root cause" in r.text
    print(f"FATAL signal: {'present in input' if fatal_in else 'n/a'} -> "
          f"{'SURVIVED' if fatal_out else ('(no fatal)' if not fatal_in else 'LOST!')}")


def main() -> None:
    log = build_incident_log()
    show("Incident log", log)

    rag = (
        '[' + ",".join(
            f'{{"id":"chunk-{i}","source":"docs/guide.md","score":0.{90 - i},'
            f'"text":"Slides are rendered server-side in section {i}."}}'
            for i in range(40)
        ) + ']'
    )
    show("RAG / JSON chunks", rag)


if __name__ == "__main__":
    main()
