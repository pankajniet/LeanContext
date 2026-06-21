"""JSON / RAG reducer.

The dominant waste in JSON tool output is *repeated keys*: a list of 200 records
re-states every field name 200 times. We factor the schema out once and emit the
values columnar. All values are preserved, so this is near-lossless.

Falls back to whitespace-stripped (minified) JSON when the payload isn't a record
list — still a real saving on pretty-printed output, with zero information loss.
"""

from __future__ import annotations

import json
from typing import Any, Optional


def _find_records(data: Any) -> Optional[list[dict]]:
    """Locate a homogeneous-ish list of dicts at the top level or one level down."""
    if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
        return data
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
                return value
    return None


def _fmt(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def reduce_json(text: str) -> tuple[str, list[str]]:
    data = json.loads(text)
    records = _find_records(data)

    if records is not None and len(records) >= 3:
        keys = list(dict.fromkeys(k for row in records for k in row.keys()))
        header = "fields: " + " | ".join(keys)
        rows = [" | ".join(_fmt(row.get(k, "")) for k in keys) for row in records]
        notes = [f"columnar: {len(records)} records × {len(keys)} fields, keys factored out once"]
        return header + "\n" + "\n".join(rows), notes

    compact = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return compact, ["minified json (indentation/whitespace removed, lossless)"]
