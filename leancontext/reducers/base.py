"""The shape every reducer registers with.

A reducer bundles three things: the kind name, a detector that says whether a
payload is this kind, and the reduce function. Detection priority is explicit
(lower runs first), so the order is clear and stable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Reducer:
    kind: str
    detect: Callable[[str], bool]
    reduce: Callable[[str], tuple[str, list[str]]]
    priority: int
