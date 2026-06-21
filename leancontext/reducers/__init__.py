"""Typed reducers. Each is a pure function: ``str -> (reduced_str, notes)``."""

from .diff import reduce_diff
from .html import reduce_html
from .json_data import reduce_json
from .logs import reduce_logs
from .stacktrace import reduce_stacktrace

__all__ = ["reduce_logs", "reduce_json", "reduce_diff", "reduce_stacktrace", "reduce_html"]
