"""Stack-trace reducer.

The exception (last line) and the boundary frames are the signal; the deep middle
of the call stack is usually noise. Keeps the header, the first frame, the last two
frames, and the full exception/tail verbatim; collapses the middle with a count.
Raises on non-tracebacks → core falls back to passthrough (fail open).
"""

from __future__ import annotations

_KEEP_HEAD = 1
_KEEP_TAIL = 2


def reduce_stacktrace(text: str) -> tuple[str, list[str]]:
    lines = text.splitlines()
    file_idx = [i for i, ln in enumerate(lines) if ln.lstrip().startswith('File "')]
    if not file_idx:
        raise ValueError("not a python traceback")

    header = lines[: file_idx[0]]
    frames = [
        lines[start : (file_idx[k + 1] if k + 1 < len(file_idx) else len(lines))]
        for k, start in enumerate(file_idx)
    ]

    # Peel the trailing non-indented lines off the last frame: that's the exception.
    last = frames[-1]
    split = len(last)
    for m in range(1, len(last)):
        if last[m].strip() and not last[m].startswith((" ", "\t")):
            split = m
            break
    tail = last[split:]
    frames[-1] = last[:split]

    out = list(header)
    if len(frames) <= _KEEP_HEAD + _KEEP_TAIL + 1:
        for fr in frames:
            out.extend(fr)
    else:
        for fr in frames[:_KEEP_HEAD]:
            out.extend(fr)
        out.append(f"  ⟪… {len(frames) - _KEEP_HEAD - _KEEP_TAIL} stack frames hidden⟫")
        for fr in frames[-_KEEP_TAIL:]:
            out.extend(fr)
    out.extend(tail)

    notes = [f"kept {min(len(frames), _KEEP_HEAD + _KEEP_TAIL)} of {len(frames)} frames + exception"]
    return "\n".join(out), notes
