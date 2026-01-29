"""Smoke tests verifying package structure is intact."""

import os
import pytest

needs_api_key = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


def test_import_stream_utils():
    from EvoScientist.stream.utils import (
        is_success,
        format_tool_compact,
        truncate,
        has_args,
        count_lines,
        truncate_with_line_hint,
    )
    assert callable(is_success)


def test_import_stream_emitter():
    from EvoScientist.stream.emitter import StreamEventEmitter, StreamEvent
    assert callable(StreamEventEmitter.thinking)


def test_import_stream_tracker():
    from EvoScientist.stream.tracker import ToolCallTracker, ToolCallInfo
    assert ToolCallTracker is not None


def test_import_backends():
    from EvoScientist.backends import (
        validate_command,
        convert_virtual_paths_in_command,
        CustomSandboxBackend,
        ReadOnlyFilesystemBackend,
    )
    assert callable(validate_command)


def test_import_prompts():
    from EvoScientist.prompts import get_system_prompt, RESEARCHER_INSTRUCTIONS
    assert callable(get_system_prompt)


def test_import_tools():
    from EvoScientist.tools import think_tool
    assert think_tool is not None
    assert hasattr(think_tool, "invoke")


@needs_api_key
def test_import_package_exports():
    from EvoScientist import EvoScientist_agent, create_cli_agent
    # Just verify they are importable; don't call them without API key
    assert EvoScientist_agent is not None
