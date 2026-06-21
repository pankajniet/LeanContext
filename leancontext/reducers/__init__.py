"""Typed reducers.

Each reducer module exposes a ``REDUCER`` (kind, detector, reduce function,
priority). ``REGISTRY`` is the ordered list the core iterates for detection and
dispatch, so adding a reducer means adding one module and listing it here.
"""

from .base import Reducer
from .diff import REDUCER as _diff
from .diff import reduce_diff
from .html import REDUCER as _html
from .html import reduce_html
from .json_data import REDUCER as _json
from .json_data import reduce_json
from .logs import REDUCER as _logs
from .logs import reduce_logs
from .stacktrace import REDUCER as _stacktrace
from .stacktrace import reduce_stacktrace

# Detection runs in priority order (lowest first): json, stacktrace, diff, html, log.
REGISTRY: list[Reducer] = sorted(
    [_json, _stacktrace, _diff, _html, _logs], key=lambda r: r.priority
)

__all__ = [
    "Reducer",
    "REGISTRY",
    "reduce_logs",
    "reduce_json",
    "reduce_diff",
    "reduce_stacktrace",
    "reduce_html",
]
