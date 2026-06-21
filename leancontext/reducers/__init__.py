"""Typed reducers. Each is a pure function: ``str -> (reduced_str, notes)``."""

from .json_data import reduce_json
from .logs import reduce_logs

__all__ = ["reduce_logs", "reduce_json"]
