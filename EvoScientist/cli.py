"""
EvoScientist Agent CLI

Command-line interface with streaming output for the EvoScientist research agent.

Features:
- Thinking panel (blue) - shows model reasoning
- Tool calls with status indicators (green/yellow/red dots)
- Tool results in tree format with folding
- Response panel (green) - shows final response
- Thread ID support for multi-turn conversations
- Interactive mode with prompt_toolkit
"""

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime
from typing import Any, AsyncIterator

from dotenv import load_dotenv  # type: ignore[import-untyped]
from prompt_toolkit import PromptSession  # type: ignore[import-untyped]
from prompt_toolkit.history import FileHistory  # type: ignore[import-untyped]
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory  # type: ignore[import-untyped]
from prompt_toolkit.formatted_text import HTML  # type: ignore[import-untyped]
from rich.console import Console, Group  # type: ignore[import-untyped]
from rich.panel import Panel  # type: ignore[import-untyped]
from rich.markdown import Markdown  # type: ignore[import-untyped]
from rich.live import Live  # type: ignore[import-untyped]
from rich.text import Text  # type: ignore[import-untyped]
from rich.spinner import Spinner  # type: ignore[import-untyped]
from langchain_core.messages import AIMessage, AIMessageChunk  # type: ignore[import-untyped]

from .stream import (
    StreamEventEmitter,
    ToolCallTracker,
    ToolResultFormatter,
    DisplayLimits,
    ToolStatus,
    format_tool_compact,
    is_success,
)

load_dotenv(override=True)

console = Console(
    legacy_windows=(sys.platform == 'win32'),
    no_color=os.getenv('NO_COLOR') is not None,
)

formatter = ToolResultFormatter()


# =============================================================================
# Stream event generator
# =============================================================================

async def stream_agent_events(agent: Any, message: str, thread_id: str) -> AsyncIterator[dict]:
    """Stream events from the agent graph using async iteration.

    Uses agent.astream() with subgraphs=True to see sub-agent activity.

    Args:
        agent: Compiled state graph from create_deep_agent()
        message: User message
        thread_id: Thread ID for conversation persistence

    Yields:
        Event dicts: thinking, text, tool_call, tool_result,
                     subagent_start, subagent_tool_call, subagent_tool_result, subagent_end,
                     done, error
    """
    config = {"configurable": {"thread_id": thread_id}}
    emitter = StreamEventEmitter()
    tracker = ToolCallTracker()
    full_response = ""

    # Track sub-agent names by root namespace element
    _subagent_names: dict[str, str] = {}  # root_ns_element → display name
    # Track which task tool_call_ids have been announced
    _announced_tasks: set[str] = set()

    def _get_subagent_name(namespace: tuple) -> str | None:
        """Get sub-agent name from namespace, or None if main agent.

        Any non-empty namespace is a sub-agent. Name is resolved by checking
        all registered names for a prefix match against namespace elements.
        """
        if not namespace:
            return None
        root = str(namespace[0]) if namespace else ""
        # Exact match
        if root in _subagent_names:
            return _subagent_names[root]
        # Prefix match: namespace root might be "task:abc123" and we
        # registered "task:call_xyz" — check if any registered key
        # appears as a substring of the root or vice versa
        for key, name in _subagent_names.items():
            if key in root or root in key:
                _subagent_names[root] = name  # cache for next lookup
                return name
        # Auto-register: infer from namespace string
        if ":" in root:
            inferred = root.split(":")[0]
        else:
            inferred = root
        name = inferred or "sub-agent"
        _subagent_names[root] = name
        return name

    try:
        async for chunk in agent.astream(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            stream_mode="messages",
            subgraphs=True,
        ):
            # With subgraphs=True, event is (namespace, (message, metadata))
            namespace: tuple = ()
            data: Any = chunk

            if isinstance(chunk, tuple) and len(chunk) >= 2:
                first = chunk[0]
                if isinstance(first, tuple):
                    # (namespace_tuple, (message, metadata))
                    namespace = first
                    data = chunk[1]
                else:
                    # (message, metadata) — no namespace
                    data = chunk

            # Unpack message from data
            msg: Any
            if isinstance(data, tuple) and len(data) >= 2:
                msg = data[0]
            else:
                msg = data

            subagent = _get_subagent_name(namespace)

            # Process AIMessageChunk / AIMessage
            if isinstance(msg, (AIMessageChunk, AIMessage)):
                if subagent:
                    # Sub-agent content — emit sub-agent events
                    for ev in _process_chunk_content(msg, emitter, tracker):
                        if ev.type == "tool_call":
                            yield emitter.subagent_tool_call(
                                subagent, ev.data["name"], ev.data["args"], ev.data.get("id", "")
                            ).data
                        # Skip text/thinking from sub-agents (too noisy)

                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            name = tc.get("name", "")
                            args = tc.get("args", {})
                            tool_id = tc.get("id", "")
                            # Skip empty-name chunks (incomplete streaming fragments)
                            if not name and not tool_id:
                                continue
                            yield emitter.subagent_tool_call(
                                subagent, name, args if isinstance(args, dict) else {}, tool_id
                            ).data
                else:
                    # Main agent content
                    for ev in _process_chunk_content(msg, emitter, tracker):
                        if ev.type == "text":
                            full_response += ev.data.get("content", "")
                        yield ev.data

                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for ev in _process_tool_calls(msg.tool_calls, emitter, tracker):
                            yield ev.data
                            # Detect task tool calls → announce sub-agent
                            tc_data = ev.data
                            if tc_data.get("name") == "task":
                                tool_id = tc_data.get("id", "")
                                if tool_id and tool_id not in _announced_tasks:
                                    _announced_tasks.add(tool_id)
                                    args = tc_data.get("args", {})
                                    sa_name = args.get("subagent_type", "").strip()
                                    desc = args.get("description", "").strip()
                                    # Use subagent_type as name; fall back to description snippet
                                    if not sa_name:
                                        sa_name = desc[:30] + "..." if len(desc) > 30 else desc
                                    if not sa_name:
                                        sa_name = "sub-agent"
                                    # Pre-register name so namespace lookup finds it
                                    _subagent_names[f"task:{tool_id}"] = sa_name
                                    yield emitter.subagent_start(sa_name, desc).data

            # Process ToolMessage (tool execution result)
            elif hasattr(msg, "type") and msg.type == "tool":
                if subagent:
                    name = getattr(msg, "name", "unknown")
                    raw_content = str(getattr(msg, "content", ""))
                    content = raw_content[:DisplayLimits.TOOL_RESULT_MAX]
                    success = is_success(content)
                    yield emitter.subagent_tool_result(subagent, name, content, success).data
                else:
                    for ev in _process_tool_result(msg, emitter, tracker):
                        yield ev.data
                    # Check if this is a task result → sub-agent ended
                    name = getattr(msg, "name", "")
                    if name == "task":
                        tool_call_id = getattr(msg, "tool_call_id", "")
                        # Find the sub-agent name for this task
                        sa_key = f"task:{tool_call_id}"
                        sa_name = _subagent_names.get(sa_key, "sub-agent")
                        yield emitter.subagent_end(sa_name).data

    except Exception as e:
        yield emitter.error(str(e)).data
        raise

    yield emitter.done(full_response).data


def _process_chunk_content(chunk, emitter: StreamEventEmitter, tracker: ToolCallTracker):
    """Process content blocks from an AI message chunk."""
    content = chunk.content

    if isinstance(content, str):
        if content:
            yield emitter.text(content)
            return

    blocks = None
    if hasattr(chunk, "content_blocks"):
        try:
            blocks = chunk.content_blocks
        except Exception:
            blocks = None

    if blocks is None:
        if isinstance(content, dict):
            blocks = [content]
        elif isinstance(content, list):
            blocks = content
        else:
            return

    for raw_block in blocks:
        block = raw_block
        if not isinstance(block, dict):
            if hasattr(block, "model_dump"):
                block = block.model_dump()
            elif hasattr(block, "dict"):
                block = block.dict()
            else:
                continue

        block_type = block.get("type")

        if block_type in ("thinking", "reasoning"):
            thinking_text = block.get("thinking") or block.get("reasoning") or ""
            if thinking_text:
                yield emitter.thinking(thinking_text)

        elif block_type == "text":
            text = block.get("text") or block.get("content") or ""
            if text:
                yield emitter.text(text)

        elif block_type in ("tool_use", "tool_call"):
            tool_id = block.get("id", "")
            name = block.get("name", "")
            args = block.get("input") if block_type == "tool_use" else block.get("args")
            args_payload = args if isinstance(args, dict) else {}

            if tool_id:
                tracker.update(tool_id, name=name, args=args_payload)
                if tracker.is_ready(tool_id):
                    tracker.mark_emitted(tool_id)
                    yield emitter.tool_call(name, args_payload, tool_id)

        elif block_type == "input_json_delta":
            partial_json = block.get("partial_json", "")
            if partial_json:
                tracker.append_json_delta(partial_json, block.get("index", 0))

        elif block_type == "tool_call_chunk":
            tool_id = block.get("id", "")
            name = block.get("name", "")
            if tool_id:
                tracker.update(tool_id, name=name)
            partial_args = block.get("args", "")
            if isinstance(partial_args, str) and partial_args:
                tracker.append_json_delta(partial_args, block.get("index", 0))


def _process_tool_calls(tool_calls: list, emitter: StreamEventEmitter, tracker: ToolCallTracker):
    """Process tool_calls from chunk.tool_calls attribute."""
    for tc in tool_calls:
        tool_id = tc.get("id", "")
        if tool_id:
            name = tc.get("name", "")
            args = tc.get("args", {})
            args_payload = args if isinstance(args, dict) else {}

            tracker.update(tool_id, name=name, args=args_payload)
            if tracker.is_ready(tool_id):
                tracker.mark_emitted(tool_id)
                yield emitter.tool_call(name, args_payload, tool_id)


def _process_tool_result(chunk, emitter: StreamEventEmitter, tracker: ToolCallTracker):
    """Process a ToolMessage result."""
    tracker.finalize_all()

    # Re-emit all tool calls with complete args
    for info in tracker.get_all():
        yield emitter.tool_call(info.name, info.args, info.id)

    name = getattr(chunk, "name", "unknown")
    raw_content = str(getattr(chunk, "content", ""))
    content = raw_content[:DisplayLimits.TOOL_RESULT_MAX]
    if len(raw_content) > DisplayLimits.TOOL_RESULT_MAX:
        content += "\n... (truncated)"

    success = is_success(content)
    yield emitter.tool_result(name, content, success)


# =============================================================================
# Stream state
# =============================================================================

class SubAgentState:
    """Tracks a single sub-agent's activity."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.tool_calls: list[dict] = []
        self.tool_results: list[dict] = []
        self._result_map: dict[str, dict] = {}  # tool_call_id → result
        self.is_active = True

    def add_tool_call(self, name: str, args: dict, tool_id: str = ""):
        # Skip empty-name calls without an id (incomplete streaming chunks)
        if not name and not tool_id:
            return
        tc_data = {"id": tool_id, "name": name, "args": args}
        if tool_id:
            for i, tc in enumerate(self.tool_calls):
                if tc.get("id") == tool_id:
                    # Merge: keep the non-empty name/args
                    if name:
                        self.tool_calls[i]["name"] = name
                    if args:
                        self.tool_calls[i]["args"] = args
                    return
        # Skip if name is empty and we can't deduplicate by id
        if not name:
            return
        self.tool_calls.append(tc_data)

    def add_tool_result(self, name: str, content: str, success: bool = True):
        result = {"name": name, "content": content, "success": success}
        self.tool_results.append(result)
        # Try to match result to the first unmatched tool call with same name
        for tc in self.tool_calls:
            tc_id = tc.get("id", "")
            tc_name = tc.get("name", "")
            if tc_id and tc_id not in self._result_map and tc_name == name:
                self._result_map[tc_id] = result
                return
        # Fallback: match first unmatched tool call
        for tc in self.tool_calls:
            tc_id = tc.get("id", "")
            if tc_id and tc_id not in self._result_map:
                self._result_map[tc_id] = result
                return

    def get_result_for(self, tc: dict) -> dict | None:
        """Get matched result for a tool call."""
        tc_id = tc.get("id", "")
        if tc_id:
            return self._result_map.get(tc_id)
        # Fallback: index-based matching
        try:
            idx = self.tool_calls.index(tc)
            if idx < len(self.tool_results):
                return self.tool_results[idx]
        except ValueError:
            pass
        return None


class StreamState:
    """Accumulates stream state for display updates."""

    def __init__(self):
        self.thinking_text = ""
        self.response_text = ""
        self.tool_calls = []
        self.tool_results = []
        self.is_thinking = False
        self.is_responding = False
        self.is_processing = False
        # Sub-agent tracking
        self.subagents: list[SubAgentState] = []
        self._subagent_map: dict[str, SubAgentState] = {}  # name → state

    def _get_or_create_subagent(self, name: str, description: str = "") -> SubAgentState:
        if name not in self._subagent_map:
            # Check if there's a generic "sub-agent" entry that should be merged
            # This happens when namespace events arrive before the task tool call
            # registers the proper name
            if name != "sub-agent" and "sub-agent" in self._subagent_map:
                old_sa = self._subagent_map.pop("sub-agent")
                old_sa.name = name
                if description:
                    old_sa.description = description
                self._subagent_map[name] = old_sa
                return old_sa
            sa = SubAgentState(name, description)
            self.subagents.append(sa)
            self._subagent_map[name] = sa
        elif description and not self._subagent_map[name].description:
            self._subagent_map[name].description = description
        return self._subagent_map[name]

    def handle_event(self, event: dict) -> str:
        """Process a single stream event, update internal state, return event type."""
        event_type: str = event.get("type", "")

        if event_type == "thinking":
            self.is_thinking = True
            self.is_responding = False
            self.is_processing = False
            self.thinking_text += event.get("content", "")

        elif event_type == "text":
            self.is_thinking = False
            self.is_responding = True
            self.is_processing = False
            self.response_text += event.get("content", "")

        elif event_type == "tool_call":
            self.is_thinking = False
            self.is_responding = False
            self.is_processing = False

            tool_id = event.get("id", "")
            tc_data = {
                "id": tool_id,
                "name": event.get("name", "unknown"),
                "args": event.get("args", {}),
            }

            if tool_id:
                updated = False
                for i, tc in enumerate(self.tool_calls):
                    if tc.get("id") == tool_id:
                        self.tool_calls[i] = tc_data
                        updated = True
                        break
                if not updated:
                    self.tool_calls.append(tc_data)
            else:
                self.tool_calls.append(tc_data)

        elif event_type == "tool_result":
            self.is_processing = True
            self.tool_results.append({
                "name": event.get("name", "unknown"),
                "content": event.get("content", ""),
            })

        elif event_type == "subagent_start":
            name = event.get("name", "sub-agent")
            desc = event.get("description", "")
            sa = self._get_or_create_subagent(name, desc)
            sa.is_active = True

        elif event_type == "subagent_tool_call":
            sa_name = event.get("subagent", "sub-agent")
            sa = self._get_or_create_subagent(sa_name)
            sa.add_tool_call(
                event.get("name", "unknown"),
                event.get("args", {}),
                event.get("id", ""),
            )

        elif event_type == "subagent_tool_result":
            sa_name = event.get("subagent", "sub-agent")
            sa = self._get_or_create_subagent(sa_name)
            sa.add_tool_result(
                event.get("name", "unknown"),
                event.get("content", ""),
                event.get("success", True),
            )

        elif event_type == "subagent_end":
            name = event.get("name", "sub-agent")
            if name in self._subagent_map:
                self._subagent_map[name].is_active = False

        elif event_type == "done":
            self.is_processing = False
            if not self.response_text:
                self.response_text = event.get("response", "")

        elif event_type == "error":
            self.is_processing = False
            self.is_thinking = False
            self.is_responding = False
            error_msg = event.get("message", "Unknown error")
            self.response_text += f"\n\n[Error] {error_msg}"

        return event_type

    def get_display_args(self) -> dict:
        """Get kwargs for create_streaming_display()."""
        return {
            "thinking_text": self.thinking_text,
            "response_text": self.response_text,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "is_thinking": self.is_thinking,
            "is_responding": self.is_responding,
            "is_processing": self.is_processing,
            "subagents": self.subagents,
        }


# =============================================================================
# Display functions
# =============================================================================

def _parse_todo_items(content: str) -> list[dict] | None:
    """Parse todo items from write_todos output.

    Attempts to extract a list of dicts with 'status' and 'content' keys
    from the tool result string. Returns None if parsing fails.
    """
    import ast
    import json

    content = content.strip()

    # Try JSON first
    try:
        data = json.loads(content)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Try Python literal
    try:
        data = ast.literal_eval(content)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data
    except (ValueError, SyntaxError):
        pass

    # Try to find a list embedded in the output
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            try:
                data = json.loads(line)
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, ValueError):
                try:
                    data = ast.literal_eval(line)
                    if isinstance(data, list):
                        return data
                except (ValueError, SyntaxError):
                    pass

    return None


def _build_todo_stats(items: list[dict]) -> str:
    """Build stats string like '2 active | 1 pending | 3 done'."""
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status", "todo")).lower()
        # Normalize status names
        if status in ("done", "completed", "complete"):
            status = "done"
        elif status in ("active", "in_progress", "in-progress", "working"):
            status = "active"
        else:
            status = "pending"
        counts[status] = counts.get(status, 0) + 1

    parts = []
    for key in ("active", "pending", "done"):
        if counts.get(key, 0) > 0:
            parts.append(f"{counts[key]} {key}")
    return " | ".join(parts) if parts else f"{len(items)} items"


def _format_single_todo(item: dict) -> Text:
    """Format a single todo item with status symbol."""
    status = str(item.get("status", "todo")).lower()
    content_text = str(item.get("content", item.get("task", item.get("title", ""))))

    if status in ("done", "completed", "complete"):
        symbol = "\u2713"
        label = "done  "
        style = "green dim"
    elif status in ("active", "in_progress", "in-progress", "working"):
        symbol = "\u25cf"
        label = "active"
        style = "yellow"
    else:
        symbol = "\u25cb"
        label = "todo  "
        style = "dim"

    line = Text()
    line.append(f"    {symbol} ", style=style)
    line.append(label, style=style)
    line.append(" ", style="dim")
    # Truncate long content
    if len(content_text) > 60:
        content_text = content_text[:57] + "..."
    line.append(content_text, style=style)
    return line


def format_tool_result_compact(_name: str, content: str, max_lines: int = 5) -> list:
    """Format tool result as tree output.

    Special handling for write_todos: shows formatted checklist with status symbols.
    """
    elements = []

    if not content.strip():
        elements.append(Text("  \u2514 (empty)", style="dim"))
        return elements

    # Special handling for write_todos
    if _name == "write_todos":
        items = _parse_todo_items(content)
        if items:
            stats = _build_todo_stats(items)
            stats_line = Text()
            stats_line.append("  \u2514 ", style="dim")
            stats_line.append(stats, style="dim")
            elements.append(stats_line)
            elements.append(Text("", style="dim"))  # blank line

            max_preview = 4
            for item in items[:max_preview]:
                elements.append(_format_single_todo(item))

            remaining = len(items) - max_preview
            if remaining > 0:
                elements.append(Text(f"    ... {remaining} more", style="dim italic"))

            return elements

    lines = content.strip().split("\n")
    total_lines = len(lines)

    display_lines = lines[:max_lines]
    for i, line in enumerate(display_lines):
        prefix = "\u2514" if i == 0 else " "
        if len(line) > 80:
            line = line[:77] + "..."
        style = "dim" if is_success(content) else "red dim"
        elements.append(Text(f"  {prefix} {line}", style=style))

    remaining = total_lines - max_lines
    if remaining > 0:
        elements.append(Text(f"    ... +{remaining} lines", style="dim italic"))

    return elements


def _render_tool_call_line(tc: dict, tr: dict | None) -> Text:
    """Render a single tool call line with status indicator."""
    is_task = tc.get('name', '').lower() == 'task'

    if tr is not None:
        content = tr.get('content', '')
        if is_success(content):
            style = "bold green"
            indicator = "\u2713" if is_task else ToolStatus.SUCCESS.value
        else:
            style = "bold red"
            indicator = "\u2717" if is_task else ToolStatus.ERROR.value
    else:
        style = "bold yellow" if not is_task else "bold cyan"
        indicator = "\u25b6" if is_task else ToolStatus.RUNNING.value

    tool_compact = format_tool_compact(tc['name'], tc.get('args'))
    tool_text = Text()
    tool_text.append(f"{indicator} ", style=style)
    tool_text.append(tool_compact, style=style)
    return tool_text


def _render_subagent_section(sa: 'SubAgentState', compact: bool = False) -> list:
    """Render a sub-agent's activity as a compact indented section.

    Args:
        sa: Sub-agent state to render
        compact: If True, render minimal 1-2 line summary (for final display)

    Completed tools are collapsed into a summary line.
    Only the currently running tool is shown expanded.
    """
    elements = []
    BORDER = "dim cyan" if sa.is_active else "dim"

    # Filter out tool calls with empty names
    valid_calls = [tc for tc in sa.tool_calls if tc.get("name")]

    # Split into completed and pending
    completed = []
    pending = []
    for tc in valid_calls:
        tr = sa.get_result_for(tc)
        if tr is not None:
            completed.append((tc, tr))
        else:
            pending.append(tc)

    succeeded = sum(1 for _, tr in completed if tr.get("success", True))
    failed = len(completed) - succeeded

    # --- Compact mode: 1-2 line summary for final display ---
    if compact:
        line = Text()
        if not sa.is_active:
            line.append("  \u2713 ", style="green")
            line.append(sa.name, style="bold green")
        else:
            line.append("  \u25b6 ", style="cyan")
            line.append(sa.name, style="bold cyan")
        if sa.description:
            desc = sa.description[:50] + "..." if len(sa.description) > 50 else sa.description
            line.append(f" \u2014 {desc}", style="dim")
        elements.append(line)
        # Stats line
        if valid_calls:
            stats = Text("    ")
            stats.append(f"{succeeded} completed", style="dim green")
            if failed > 0:
                stats.append(f" \u00b7 {failed} failed", style="dim red")
            if pending:
                stats.append(f" \u00b7 {len(pending)} running", style="dim yellow")
            elements.append(stats)
        return elements

    # --- Full mode: bordered section for Live streaming ---
    # Shows every tool call individually with status indicators

    # Header
    header = Text()
    header.append("  \u250c ", style=BORDER)
    if sa.is_active:
        header.append(sa.name, style="bold cyan")
    else:
        header.append(sa.name, style="bold green")
        header.append(" \u2713", style="green")
    if sa.description:
        desc = sa.description[:55] + "..." if len(sa.description) > 55 else sa.description
        header.append(f" \u2014 {desc}", style="dim")
    elements.append(header)

    # Show every tool call with its status
    for tc, tr in completed:
        tc_line = Text("  \u2502 ", style=BORDER)
        tc_name = format_tool_compact(tc["name"], tc.get("args"))
        if tr.get("success", True):
            tc_line.append(f"\u2713 {tc_name}", style="green")
        else:
            tc_line.append(f"\u2717 {tc_name}", style="red")
            # Show first line of error
            content = tr.get("content", "")
            first_line = content.strip().split("\n")[0][:70]
            if first_line:
                err_line = Text("  \u2502   ", style=BORDER)
                err_line.append(f"\u2514 {first_line}", style="red dim")
                elements.append(tc_line)
                elements.append(err_line)
                continue
        elements.append(tc_line)

    # Pending/running tools
    for tc in pending:
        tc_line = Text("  \u2502 ", style=BORDER)
        tc_name = format_tool_compact(tc["name"], tc.get("args"))
        tc_line.append(f"\u25cf {tc_name}", style="bold yellow")
        elements.append(tc_line)
        spinner_line = Text("  \u2502   ", style=BORDER)
        spinner_line.append("\u21bb running...", style="yellow dim")
        elements.append(spinner_line)

    # Footer
    if not sa.is_active:
        total = len(valid_calls)
        footer = Text(f"  \u2514 done ({total} tools)", style="dim green")
        elements.append(footer)
    elif valid_calls:
        footer = Text("  \u2514 running...", style="dim cyan")
        elements.append(footer)

    return elements


def create_streaming_display(
    thinking_text: str = "",
    response_text: str = "",
    tool_calls: list | None = None,
    tool_results: list | None = None,
    is_thinking: bool = False,
    is_responding: bool = False,
    is_waiting: bool = False,
    is_processing: bool = False,
    show_thinking: bool = True,
    subagents: list | None = None,
) -> Any:
    """Create Rich display layout for streaming output.

    Returns:
        Rich Group for Live display
    """
    elements = []
    tool_calls = tool_calls or []
    tool_results = tool_results or []
    subagents = subagents or []

    # Initial waiting state
    if is_waiting and not thinking_text and not response_text and not tool_calls:
        spinner = Spinner("dots", text=" Thinking...", style="cyan")
        elements.append(spinner)
        return Group(*elements)

    # Thinking panel
    if show_thinking and thinking_text:
        thinking_title = "Thinking"
        if is_thinking:
            thinking_title += " ..."
        display_thinking = thinking_text
        if len(display_thinking) > DisplayLimits.THINKING_STREAM:
            display_thinking = "..." + display_thinking[-DisplayLimits.THINKING_STREAM:]
        elements.append(Panel(
            Text(display_thinking, style="dim"),
            title=thinking_title,
            border_style="blue",
            padding=(0, 1),
        ))

    # Tool calls and results paired display
    # Collapse older completed tools to prevent overflow in Live mode
    MAX_VISIBLE_TOOLS = 4

    if tool_calls:
        # Split into completed and pending/running
        completed_tools = []
        recent_tools = []  # last few completed + all pending

        for i, tc in enumerate(tool_calls):
            has_result = i < len(tool_results)
            tr = tool_results[i] if has_result else None
            if has_result:
                completed_tools.append((tc, tr))
            else:
                recent_tools.append((tc, None))

        # Determine how many completed tools to show
        # Keep the last few completed + all pending within MAX_VISIBLE_TOOLS
        slots_for_completed = max(0, MAX_VISIBLE_TOOLS - len(recent_tools))
        hidden_completed = completed_tools[:-slots_for_completed] if slots_for_completed and len(completed_tools) > slots_for_completed else (completed_tools if not slots_for_completed else [])
        visible_completed = completed_tools[-slots_for_completed:] if slots_for_completed else []

        # Summary line for hidden completed tools
        if hidden_completed:
            ok = sum(1 for _, tr in hidden_completed if is_success(tr.get('content', '')))
            fail = len(hidden_completed) - ok
            summary = Text()
            summary.append(f"\u2713 {ok} completed", style="dim green")
            if fail > 0:
                summary.append(f" | {fail} failed", style="dim red")
            elements.append(summary)

        # Render visible completed tools (compact: 1 line each, no result expansion)
        for tc, tr in visible_completed:
            elements.append(_render_tool_call_line(tc, tr))
            # Only expand result for write_todos (useful) or errors
            content = tr.get('content', '') if tr else ''
            if tc.get('name') == 'write_todos' or (tr and not is_success(content)):
                result_elements = format_tool_result_compact(
                    tr['name'],
                    content,
                    max_lines=5,
                )
                elements.extend(result_elements)

        # Render pending/running tools (expanded with spinner)
        for tc, tr in recent_tools:
            elements.append(_render_tool_call_line(tc, tr))
            if tc.get('name') != 'task':
                spinner = Spinner("dots", text=" Running...", style="yellow")
                elements.append(spinner)

    # Sub-agent activity sections
    for sa in subagents:
        if sa.tool_calls or sa.is_active:
            elements.extend(_render_subagent_section(sa))

    # Processing state after tool execution
    if is_processing and not is_thinking and not is_responding and not response_text:
        # Check if any sub-agent is active
        any_active = any(sa.is_active for sa in subagents)
        if not any_active:
            spinner = Spinner("dots", text=" Analyzing results...", style="cyan")
            elements.append(spinner)

    # Response text display logic
    has_pending_tools = len(tool_calls) > len(tool_results)
    any_active_subagent = any(sa.is_active for sa in subagents)
    has_used_tools = len(tool_calls) > 0

    if response_text and not has_pending_tools and not any_active_subagent:
        if has_used_tools:
            # Tools were used — treat all text as intermediate during Live streaming.
            # Final rendering is handled by display_final_results().
            preview = response_text
            if len(preview) > 200:
                preview = "..." + preview[-197:]
            for line in preview.strip().split("\n")[-3:]:
                if line.strip():
                    elements.append(Text(f"    {line.strip()}", style="dim italic"))
        else:
            # Pure text response (no tools used) — render as Markdown
            elements.append(Text(""))  # blank separator
            elements.append(Markdown(response_text))
    elif is_responding and not thinking_text and not has_pending_tools:
        elements.append(Text("Generating response...", style="dim"))

    return Group(*elements) if elements else Text("Processing...", style="dim")


def display_final_results(
    state: StreamState,
    thinking_max_length: int = DisplayLimits.THINKING_FINAL,
    show_thinking: bool = True,
    show_tools: bool = True,
) -> None:
    """Display final results after streaming completes."""
    if show_thinking and state.thinking_text:
        display_thinking = state.thinking_text
        if len(display_thinking) > thinking_max_length:
            half = thinking_max_length // 2
            display_thinking = display_thinking[:half] + "\n\n... (truncated) ...\n\n" + display_thinking[-half:]
        console.print(Panel(
            Text(display_thinking, style="dim"),
            title="Thinking",
            border_style="blue",
        ))

    if show_tools and state.tool_calls:
        shown_sa_names: set[str] = set()

        for i, tc in enumerate(state.tool_calls):
            has_result = i < len(state.tool_results)
            tr = state.tool_results[i] if has_result else None
            content = tr.get('content', '') if tr is not None else ''
            is_task = tc.get('name', '').lower() == 'task'

            # Task tools: show delegation line + compact sub-agent summary
            if is_task:
                console.print(_render_tool_call_line(tc, tr))
                sa_name = tc.get('args', {}).get('subagent_type', '')
                task_desc = tc.get('args', {}).get('description', '')
                matched_sa = None
                for sa in state.subagents:
                    if sa.name == sa_name or (task_desc and task_desc in (sa.description or '')):
                        matched_sa = sa
                        break
                if matched_sa:
                    shown_sa_names.add(matched_sa.name)
                    for elem in _render_subagent_section(matched_sa, compact=True):
                        console.print(elem)
                continue

            # Regular tools: show tool call line + result
            console.print(_render_tool_call_line(tc, tr))
            if has_result and tr is not None:
                result_elements = format_tool_result_compact(
                    tr['name'],
                    content,
                    max_lines=10,
                )
                for elem in result_elements:
                    console.print(elem)

        # Render any sub-agents not already shown via task tool calls
        for sa in state.subagents:
            if sa.name not in shown_sa_names and (sa.tool_calls or sa.is_active):
                for elem in _render_subagent_section(sa, compact=True):
                    console.print(elem)

        console.print()

    if state.response_text:
        console.print()
        console.print(Markdown(state.response_text))
        console.print()


# =============================================================================
# Async-to-sync bridge
# =============================================================================

def _run_streaming(
    agent: Any,
    message: str,
    thread_id: str,
    show_thinking: bool,
    interactive: bool,
) -> None:
    """Run async streaming and render with Rich Live display.

    Bridges the async stream_agent_events() into synchronous Rich Live rendering
    using asyncio.run().

    Args:
        agent: Compiled agent graph
        message: User message
        thread_id: Thread ID
        show_thinking: Whether to show thinking panel
        interactive: If True, use simplified final display (no panel)
    """
    state = StreamState()

    async def _consume() -> None:
        async for event in stream_agent_events(agent, message, thread_id):
            event_type = state.handle_event(event)
            live.update(create_streaming_display(
                **state.get_display_args(),
                show_thinking=show_thinking,
            ))
            if event_type in (
                "tool_call", "tool_result",
                "subagent_start", "subagent_tool_call",
                "subagent_tool_result", "subagent_end",
            ):
                live.refresh()

    with Live(console=console, refresh_per_second=10, transient=True) as live:
        live.update(create_streaming_display(is_waiting=True))
        asyncio.run(_consume())

    if interactive:
        display_final_results(
            state,
            thinking_max_length=500,
            show_thinking=False,
            show_tools=True,
        )
    else:
        console.print()
        display_final_results(
            state,
            show_tools=True,
        )


# =============================================================================
# CLI commands
# =============================================================================

EVOSCIENTIST_ASCII_LINES = [
    r" ███████╗ ██╗   ██╗  ██████╗  ███████╗  ██████╗ ██╗ ███████╗ ███╗   ██╗ ████████╗ ██╗ ███████╗ ████████╗",
    r" ██╔════╝ ██║   ██║ ██╔═══██╗ ██╔════╝ ██╔════╝ ██║ ██╔════╝ ████╗  ██║ ╚══██╔══╝ ██║ ██╔════╝ ╚══██╔══╝",
    r" █████╗   ██║   ██║ ██║   ██║ ███████╗ ██║      ██║ █████╗   ██╔██╗ ██║    ██║    ██║ ███████╗    ██║   ",
    r" ██╔══╝   ╚██╗ ██╔╝ ██║   ██║ ╚════██║ ██║      ██║ ██╔══╝   ██║╚██╗██║    ██║    ██║ ╚════██║    ██║   ",
    r" ███████╗  ╚████╔╝  ╚██████╔╝ ███████║ ╚██████╗ ██║ ███████╗ ██║ ╚████║    ██║    ██║ ███████║    ██║   ",
    r" ╚══════╝   ╚═══╝    ╚═════╝  ╚══════╝  ╚═════╝ ╚═╝ ╚══════╝ ╚═╝  ╚═══╝    ╚═╝    ╚═╝ ╚══════╝    ╚═╝   ",
]

# Blue gradient: deep navy → royal blue → sky blue → cyan
_GRADIENT_COLORS = ["#1a237e", "#1565c0", "#1e88e5", "#42a5f5", "#64b5f6", "#90caf9"]


def print_banner(thread_id: str, workspace_dir: str | None = None):
    """Print welcome banner with ASCII art logo, thread ID, and workspace path."""
    for line, color in zip(EVOSCIENTIST_ASCII_LINES, _GRADIENT_COLORS):
        console.print(Text(line, style=f"{color} bold"))
    info = Text()
    info.append("  Thread: ", style="dim")
    info.append(thread_id, style="yellow")
    if workspace_dir:
        info.append("\n  Workspace: ", style="dim")
        info.append(workspace_dir, style="cyan")
    info.append("\n  Commands: ", style="dim")
    info.append("/exit", style="bold")
    info.append(", ", style="dim")
    info.append("/new", style="bold")
    info.append(" (new session), ", style="dim")
    info.append("/thread", style="bold")
    info.append(" (show thread ID)", style="dim")
    console.print(info)
    console.print()


def cmd_interactive(agent: Any, show_thinking: bool = True, workspace_dir: str | None = None) -> None:
    """Interactive conversation mode with streaming output.

    Args:
        agent: Compiled agent graph
        show_thinking: Whether to display thinking panels
        workspace_dir: Per-session workspace directory path
    """
    thread_id = str(uuid.uuid4())
    print_banner(thread_id, workspace_dir)

    history_file = str(os.path.expanduser("~/.EvoScientist_history"))
    session = PromptSession(
        history=FileHistory(history_file),
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
    )

    while True:
        try:
            user_input = session.prompt(
                HTML('<ansigreen><b>You:</b></ansigreen> ')
            ).strip()

            if not user_input:
                continue

            # Special commands
            if user_input.lower() in ("/exit", "/quit", "/q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() == "/new":
                # New session: new workspace, new agent, new thread
                workspace_dir = _create_session_workspace()
                console.print("[dim]Loading new session...[/dim]")
                agent = _load_agent(workspace_dir=workspace_dir)
                thread_id = str(uuid.uuid4())
                console.print(f"[green]New session:[/green] [yellow]{thread_id}[/yellow]")
                console.print(f"[dim]Workspace:[/dim] [cyan]{workspace_dir}[/cyan]\n")
                continue

            if user_input.lower() == "/thread":
                console.print(f"[dim]Thread:[/dim] [yellow]{thread_id}[/yellow]")
                if workspace_dir:
                    console.print(f"[dim]Workspace:[/dim] [cyan]{workspace_dir}[/cyan]")
                console.print()
                continue

            # Stream agent response
            console.print()
            _run_streaming(agent, user_input, thread_id, show_thinking, interactive=True)

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def cmd_run(agent: Any, prompt: str, thread_id: str | None = None, show_thinking: bool = True, workspace_dir: str | None = None) -> None:
    """Single-shot execution with streaming display.

    Args:
        agent: Compiled agent graph
        prompt: User prompt
        thread_id: Optional thread ID (generates new one if None)
        show_thinking: Whether to display thinking panels
        workspace_dir: Per-session workspace directory path
    """
    thread_id = thread_id or str(uuid.uuid4())

    console.print(Panel(f"[bold cyan]Query:[/bold cyan]\n{prompt}"))
    console.print(f"[dim]Thread: {thread_id}[/dim]")
    if workspace_dir:
        console.print(f"[dim]Workspace: {workspace_dir}[/dim]")
    console.print()

    try:
        _run_streaming(agent, prompt, thread_id, show_thinking, interactive=False)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise


# =============================================================================
# Entry point
# =============================================================================

def _create_session_workspace() -> str:
    """Create a per-session workspace directory and return its path."""
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace_dir = os.path.join(".", "workspace", session_id)
    os.makedirs(workspace_dir, exist_ok=True)
    return workspace_dir


def _load_agent(workspace_dir: str | None = None):
    """Load the CLI agent (with InMemorySaver checkpointer for multi-turn).

    Args:
        workspace_dir: Optional per-session workspace directory.
    """
    from .EvoScientist import create_cli_agent
    return create_cli_agent(workspace_dir=workspace_dir)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="EvoScientist Agent - AI-powered research & code execution CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (default)
  python -m EvoScientist --interactive

  # Single-shot query
  python -m EvoScientist "What is quantum computing?"

  # Resume a conversation thread
  python -m EvoScientist --thread-id <uuid> "Follow-up question"

  # Disable thinking display
  python -m EvoScientist --no-thinking "Your query"
""",
    )

    parser.add_argument(
        "prompt",
        nargs="?",
        help="Query to execute (single-shot mode)",
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Interactive conversation mode",
    )
    parser.add_argument(
        "--thread-id",
        type=str,
        default=None,
        help="Thread ID for conversation persistence (resume session)",
    )
    parser.add_argument(
        "--no-thinking",
        action="store_true",
        help="Disable thinking display",
    )

    args = parser.parse_args()
    show_thinking = not args.no_thinking

    # Create per-session workspace
    workspace_dir = _create_session_workspace()

    # Load agent with session workspace
    console.print("[dim]Loading agent...[/dim]")
    agent = _load_agent(workspace_dir=workspace_dir)

    if args.interactive:
        cmd_interactive(agent, show_thinking=show_thinking, workspace_dir=workspace_dir)
    elif args.prompt:
        cmd_run(agent, args.prompt, thread_id=args.thread_id, show_thinking=show_thinking, workspace_dir=workspace_dir)
    else:
        # Default: interactive mode
        cmd_interactive(agent, show_thinking=show_thinking, workspace_dir=workspace_dir)


if __name__ == "__main__":
    main()
