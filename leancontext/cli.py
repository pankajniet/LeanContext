"""`leancontext reduce <file>` — see the saving on any payload from the terminal."""

from __future__ import annotations

import argparse
import sys

from .core import reduce_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="leancontext", description="Reduce a tool-output payload.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("reduce", help="reduce a file (or stdin) and report the saving")
    p.add_argument("file", nargs="?", help="path to read; omit to read stdin")
    p.add_argument("--kind", default="auto", help="force a content kind (default: auto)")
    p.add_argument("--show", action="store_true", help="print the reduced payload")

    args = parser.parse_args(argv)
    text = sys.stdin.read() if not args.file else open(args.file, encoding="utf-8").read()

    r = reduce_text(text, kind=args.kind)
    print(f"kind        : {r.kind}", file=sys.stderr)
    print(f"tokens      : {r.tokens_before} -> {r.tokens_after}", file=sys.stderr)
    print(f"saved       : {r.ratio:.0%}", file=sys.stderr)
    print(f"fidelity    : {r.fidelity:.0%}", file=sys.stderr)
    for note in r.notes:
        print(f"note        : {note}", file=sys.stderr)
    if args.show:
        print(r.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
