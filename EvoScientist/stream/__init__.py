"""
Stream module - streaming event processing for CLI display.

Provides:
- StreamEventEmitter: Standardized event creation
- ToolCallTracker: Incremental JSON parsing for tool parameters
- ToolResultFormatter: Content-aware result formatting with Rich
- Utility functions and constants
"""

from .emitter import StreamEventEmitter, StreamEvent
from .tracker import ToolCallTracker, ToolCallInfo
from .formatter import ToolResultFormatter, ContentType, FormattedResult
from .utils import (
    SUCCESS_PREFIX,
    FAILURE_PREFIX,
    ToolStatus,
    DisplayLimits,
    has_args,
    is_success,
    truncate,
    format_tool_compact,
    format_tree_output,
    count_lines,
    truncate_with_line_hint,
    get_status_symbol,
)

__all__ = [
    # Emitter
    "StreamEventEmitter",
    "StreamEvent",
    # Tracker
    "ToolCallTracker",
    "ToolCallInfo",
    # Formatter
    "ToolResultFormatter",
    "ContentType",
    "FormattedResult",
    # Utils
    "SUCCESS_PREFIX",
    "FAILURE_PREFIX",
    "ToolStatus",
    "DisplayLimits",
    "has_args",
    "is_success",
    "truncate",
    "format_tool_compact",
    "format_tree_output",
    "count_lines",
    "truncate_with_line_hint",
    "get_status_symbol",
]
